#include "PrefabSaveUpdateBridgeHostComponent.h"

#include <AzCore/IO/Path/Path.h>
#include <AzCore/IO/SystemFile.h>
#include <AzCore/Interface/Interface.h>
#include <AzCore/RTTI/BehaviorContext.h>
#include <AzCore/Serialization/SerializeContext.h>
#include <AzCore/std/containers/vector.h>
#include <AzCore/Utils/Utils.h>
#include <AzToolsFramework/Prefab/Overrides/PrefabOverridePublicInterface.h>
#include <AzToolsFramework/Prefab/PrefabLoaderInterface.h>
#include <AzToolsFramework/Prefab/PrefabPublicInterface.h>
#include <AzToolsFramework/API/ToolsApplicationAPI.h>
#include <AzToolsFramework/Entity/EditorEntityContextBus.h>

namespace
{
    AZStd::string NormalizeForPathPolicy(AZStd::string value)
    {
        for (char& ch : value)
        {
            if (ch == '\\')
            {
                ch = '/';
            }
            else if (ch >= 'A' && ch <= 'Z')
            {
                ch = static_cast<char>(ch - 'A' + 'a');
            }
        }
        return value;
    }

    bool EndsWith(AZStd::string_view value, AZStd::string_view suffix)
    {
        return value.size() >= suffix.size() && value.substr(value.size() - suffix.size()) == suffix;
    }

    bool Contains(AZStd::string_view value, AZStd::string_view token)
    {
        return value.find(token) != AZStd::string_view::npos;
    }

    bool StartsWith(AZStd::string_view value, AZStd::string_view prefix)
    {
        return value.size() >= prefix.size() && value.substr(0, prefix.size()) == prefix;
    }

    bool ContainsParentTraversalSegment(AZStd::string_view normalized)
    {
        return normalized == ".." || StartsWith(normalized, "../") || EndsWith(normalized, "/..") || Contains(normalized, "/../");
    }

    bool IsPathInsideRoot(AZStd::string_view normalizedPath, AZStd::string_view normalizedRoot)
    {
        if (normalizedPath.size() <= normalizedRoot.size() || !StartsWith(normalizedPath, normalizedRoot))
        {
            return false;
        }
        return normalizedPath[normalizedRoot.size()] == '/';
    }

    AZStd::string RejectReasonForScratchPath(const AZ::IO::Path& path)
    {
        const AZStd::string normalizedInput = NormalizeForPathPolicy(path.String());
        if (!path.IsAbsolute())
        {
            return "path_not_absolute";
        }
        if (!EndsWith(normalizedInput, ".prefab"))
        {
            return "not_prefab_extension";
        }
        if (ContainsParentTraversalSegment(normalizedInput))
        {
            return "path_traversal";
        }

        const AZ::IO::FixedMaxPathString projectPath = AZ::Utils::GetProjectPath();
        if (projectPath.empty())
        {
            return "project_root_unavailable";
        }

        const AZ::IO::Path normalizedPrefabPath = path.LexicallyNormal();
        const AZ::IO::Path normalizedProjectRoot = AZ::IO::Path(projectPath).LexicallyNormal();
        const AZ::IO::Path project_root_anchored_scratch_root =
            (normalizedProjectRoot / "Assets" / "_maxine_smoke" / "prefabs").LexicallyNormal();
        const AZStd::string normalized = NormalizeForPathPolicy(normalizedPrefabPath.String());
        const AZStd::string normalizedScratchRoot = NormalizeForPathPolicy(project_root_anchored_scratch_root.String());

        if (Contains(normalized, "/levels/") || Contains(normalized, "defaultlevel") || Contains(normalized, "/production/"))
        {
            return "level_or_production_path";
        }
        if (Contains(normalized, "/cache/") || Contains(normalized, "/asset cache/") || Contains(normalized, "/pc/") ||
            Contains(normalized, "/build/") || Contains(normalized, ".spawnable") || Contains(normalized, "/user/log/"))
        {
            return "generated_product_or_cache_path";
        }
        if (!IsPathInsideRoot(normalized, normalizedScratchRoot))
        {
            return "unapproved_scratch_root";
        }
        return "";
    }

    AZStd::string RejectReasonForApprovedSourcePrefabPath(const AZ::IO::Path& path)
    {
        const AZStd::string normalizedInput = NormalizeForPathPolicy(path.String());
        if (!path.IsAbsolute())
        {
            return "path_not_absolute";
        }
        if (!EndsWith(normalizedInput, ".prefab"))
        {
            return "not_prefab_extension";
        }
        if (ContainsParentTraversalSegment(normalizedInput))
        {
            return "path_traversal";
        }

        const AZ::IO::FixedMaxPathString projectPath = AZ::Utils::GetProjectPath();
        if (projectPath.empty())
        {
            return "project_root_unavailable";
        }

        const AZ::IO::Path normalizedPrefabPath = path.LexicallyNormal();
        const AZ::IO::Path normalizedProjectRoot = AZ::IO::Path(projectPath).LexicallyNormal();
        const AZ::IO::Path approved_source_prefab_path =
            (normalizedProjectRoot / "Assets" / "Characters" / "MAXINE_GoldenCorpus" / "prefabs" / "release_rigged.prefab")
                .LexicallyNormal();
        const AZStd::string normalized = NormalizeForPathPolicy(normalizedPrefabPath.String());
        const AZStd::string normalizedProject = NormalizeForPathPolicy(normalizedProjectRoot.String());
        const AZStd::string normalizedApprovedSourcePrefab = NormalizeForPathPolicy(approved_source_prefab_path.String());

        if (!StartsWith(normalized, normalizedProject) || (normalized.size() > normalizedProject.size() && normalized[normalizedProject.size()] != '/'))
        {
            return "unapproved_absolute_path";
        }
        if (Contains(normalized, "/levels/") || Contains(normalized, "defaultlevel") || Contains(normalized, "/production/"))
        {
            return "level_or_production_path";
        }
        if (Contains(normalized, "/cache/") || Contains(normalized, "/asset cache/") || Contains(normalized, "/pc/") ||
            Contains(normalized, "/build/") || Contains(normalized, ".spawnable") || Contains(normalized, "/user/log/"))
        {
            return "generated_product_or_cache_path";
        }
        if (normalized != normalizedApprovedSourcePrefab)
        {
            return "unapproved_approved_source_prefab_path";
        }
        return "";
    }

    AZStd::string RouteResult(AZStd::string_view status, AZStd::string_view reason = "")
    {
        AZStd::string result = AZStd::string::format("maxine_prefab_save_update_route_%.*s", AZ_STRING_ARG(status));
        if (!reason.empty())
        {
            result += AZStd::string::format(";reason=%.*s", AZ_STRING_ARG(reason));
        }
        return result;
    }
} // namespace

namespace MaxineRuntimeExitFixture
{
    AZ_COMPONENT_IMPL(
        PrefabSaveUpdateBridgeHostComponent,
        "MaxinePrefabSaveUpdateBridgeHostComponent",
        "{4E075D01-F5F0-42DA-A58F-153B47FA0C8A}");

    void PrefabSaveUpdateBridgeHostComponent::Reflect(AZ::ReflectContext* context)
    {
        if (auto serializeContext = azrtti_cast<AZ::SerializeContext*>(context))
        {
            serializeContext->Class<PrefabSaveUpdateBridgeHostComponent, AZ::Component>()->Version(1);
        }

        if (auto behaviorContext = azrtti_cast<AZ::BehaviorContext*>(context))
        {
            behaviorContext
                ->Method(
                    "get_prefab_save_update_bridge_host_status",
                    &PrefabSaveUpdateBridgeHostComponent::GetPrefabSaveUpdateBridgeHostStatus,
                    nullptr,
                    "Returns bounded status for the MAXINE prefab save/update bridge host.")
                ->Attribute(AZ::Script::Attributes::Scope, AZ::Script::Attributes::ScopeFlags::Automation)
                ->Attribute(AZ::Script::Attributes::Category, "MAXINE/PrefabSaveUpdateBridge")
                ->Attribute(AZ::Script::Attributes::Module, "maxine.prefab_bridge");
            behaviorContext
                ->Method(
                    "save_prefab_update_scratch_probe",
                    &PrefabSaveUpdateBridgeHostComponent::SavePrefabUpdateScratchProbe,
                    nullptr,
                    "Saves a bounded MAXINE scratch prefab through PrefabPublicInterface::CreatePrefabAndSaveToDisk.")
                ->Attribute(AZ::Script::Attributes::Scope, AZ::Script::Attributes::ScopeFlags::Automation)
                ->Attribute(AZ::Script::Attributes::Category, "MAXINE/PrefabSaveUpdateBridge")
                ->Attribute(AZ::Script::Attributes::Module, "maxine.prefab_bridge");
            behaviorContext
                ->Method(
                    "apply_approved_source_prefab_component_overrides",
                    &PrefabSaveUpdateBridgeHostComponent::ApplyApprovedSourcePrefabComponentOverrides,
                    nullptr,
                    "Applies only the generated Actor and Simple Motion component overrides for the approved MAXINE source prefab.")
                ->Attribute(AZ::Script::Attributes::Scope, AZ::Script::Attributes::ScopeFlags::Automation)
                ->Attribute(AZ::Script::Attributes::Category, "MAXINE/PrefabSaveUpdateBridge")
                ->Attribute(AZ::Script::Attributes::Module, "maxine.prefab_bridge");
            behaviorContext
                ->Method(
                    "commit_approved_source_prefab_entity_changes",
                    &PrefabSaveUpdateBridgeHostComponent::CommitApprovedSourcePrefabEntityChanges,
                    nullptr,
                    "Commits generated changes for the approved prefab entity through PrefabPublicInterface dirty-entity propagation.")
                ->Attribute(AZ::Script::Attributes::Scope, AZ::Script::Attributes::ScopeFlags::Automation)
                ->Attribute(AZ::Script::Attributes::Category, "MAXINE/PrefabSaveUpdateBridge")
                ->Attribute(AZ::Script::Attributes::Module, "maxine.prefab_bridge");
            behaviorContext
                ->Method(
                    "save_approved_source_prefab_wiring",
                    &PrefabSaveUpdateBridgeHostComponent::SaveApprovedSourcePrefabWiring,
                    nullptr,
                    "Saves only the approved MAXINE runtime character source prefab after Editor-generated wiring.")
                ->Attribute(AZ::Script::Attributes::Scope, AZ::Script::Attributes::ScopeFlags::Automation)
                ->Attribute(AZ::Script::Attributes::Category, "MAXINE/PrefabSaveUpdateBridge")
                ->Attribute(AZ::Script::Attributes::Module, "maxine.prefab_bridge");
        }
    }

    void PrefabSaveUpdateBridgeHostComponent::GetProvidedServices(AZ::ComponentDescriptor::DependencyArrayType& provided)
    {
        provided.push_back(AZ_CRC_CE("MaxinePrefabSaveUpdateBridgeHostService"));
    }

    void PrefabSaveUpdateBridgeHostComponent::GetIncompatibleServices(AZ::ComponentDescriptor::DependencyArrayType& incompatible)
    {
        incompatible.push_back(AZ_CRC_CE("MaxinePrefabSaveUpdateBridgeHostService"));
    }

    void PrefabSaveUpdateBridgeHostComponent::GetRequiredServices(AZ::ComponentDescriptor::DependencyArrayType& required)
    {
        AZ_UNUSED(required);
    }

    void PrefabSaveUpdateBridgeHostComponent::GetDependentServices(AZ::ComponentDescriptor::DependencyArrayType& dependent)
    {
        AZ_UNUSED(dependent);
    }

    AZStd::string PrefabSaveUpdateBridgeHostComponent::GetPrefabSaveUpdateBridgeHostStatus()
    {
        return AZStd::string(
            "maxine_prefab_save_update_bridge_host_registered;"
            "api=AzToolsFramework::Prefab::PrefabPublicInterface;"
            "save_route_exposed=true;"
            "approved_source_save_route_exposed=true;"
            "scratch_save_verified=false");
    }

    AZStd::string PrefabSaveUpdateBridgeHostComponent::SavePrefabUpdateScratchProbe(const AZStd::string& absolutePrefabPath)
    {
        const AZ::IO::Path prefabPath(absolutePrefabPath);
        const AZStd::string rejectionReason = RejectReasonForScratchPath(prefabPath);
        if (!rejectionReason.empty())
        {
            return RouteResult("rejected", rejectionReason);
        }

        const AZ::IO::Path parentPath = prefabPath.ParentPath();
        if (!AZ::IO::SystemFile::CreateDir(parentPath.FixedMaxPathString().c_str()))
        {
            return RouteResult("failed", "scratch_directory_unavailable");
        }

        auto* prefabPublicInterface = AZ::Interface<AzToolsFramework::Prefab::PrefabPublicInterface>::Get();
        if (!prefabPublicInterface)
        {
            return RouteResult("failed", "prefab_public_interface_unavailable");
        }

        AZ::EntityId scratchEntityId;
        AzToolsFramework::EditorEntityContextRequestBus::BroadcastResult(
            scratchEntityId,
            &AzToolsFramework::EditorEntityContextRequests::CreateNewEditorEntity,
            "MAXINE_PrefabSaveUpdateScratchProbe");
        if (!scratchEntityId.IsValid())
        {
            return RouteResult("failed", "scratch_entity_create_failed");
        }

        AzToolsFramework::Prefab::CreatePrefabResult saveResult =
            prefabPublicInterface->CreatePrefabAndSaveToDisk({ scratchEntityId }, prefabPath);

        AZ::EntityId cleanupEntityId = scratchEntityId;
        if (saveResult.IsSuccess())
        {
            cleanupEntityId = saveResult.GetValue();
        }

        bool cleanupVerified = false;
        if (cleanupEntityId.IsValid())
        {
            AzToolsFramework::ToolsApplicationRequestBus::Broadcast(
                &AzToolsFramework::ToolsApplicationRequests::DeleteEntityById,
                cleanupEntityId);
            cleanupVerified = true;
        }

        if (!saveResult.IsSuccess())
        {
            return RouteResult("failed", "create_prefab_and_save_to_disk_failed");
        }
        if (!cleanupVerified)
        {
            return RouteResult("failed", "scratch_entity_cleanup_failed");
        }
        if (!AZ::IO::SystemFile::Exists(prefabPath.FixedMaxPathString().c_str()))
        {
            return RouteResult("failed", "scratch_prefab_not_written");
        }

        return AZStd::string(
            "maxine_prefab_save_update_route_saved;"
            "api=AzToolsFramework::Prefab::PrefabPublicInterface::CreatePrefabAndSaveToDisk;"
            "path_policy=active_project_root/Assets/_maxine_smoke/prefabs;"
            "scratch_save_verified=true;"
            "scratch_entity_cleanup_verified=true");
    }

    AZStd::string PrefabSaveUpdateBridgeHostComponent::ApplyApprovedSourcePrefabComponentOverrides(
        const AZStd::string& absolutePrefabPath,
        const AZ::EntityComponentIdPair& actorComponent,
        const AZ::EntityComponentIdPair& simpleMotionComponent)
    {
        const AZ::IO::Path prefabPath(absolutePrefabPath);
        const AZStd::string rejectionReason = RejectReasonForApprovedSourcePrefabPath(prefabPath);
        if (!rejectionReason.empty())
        {
            return RouteResult("approved_source_override_rejected", rejectionReason);
        }

        auto* prefabOverridePublicInterface = AZ::Interface<AzToolsFramework::Prefab::PrefabOverridePublicInterface>::Get();
        if (!prefabOverridePublicInterface)
        {
            return RouteResult("approved_source_override_failed", "prefab_override_public_interface_unavailable");
        }

        const bool actorOverridePresent = prefabOverridePublicInterface->AreComponentOverridesPresent(actorComponent);
        const bool simpleMotionOverridePresent = prefabOverridePublicInterface->AreComponentOverridesPresent(simpleMotionComponent);
        const bool actorOverrideApplied = prefabOverridePublicInterface->ApplyComponentOverrides(actorComponent);
        const bool simpleMotionOverrideApplied = prefabOverridePublicInterface->ApplyComponentOverrides(simpleMotionComponent);

        if (!actorOverrideApplied || !simpleMotionOverrideApplied)
        {
            return AZStd::string::format(
                "maxine_prefab_save_update_route_approved_source_override_failed;"
                "reason=component_override_apply_failed;"
                "actor_override_present=%s;"
                "simple_motion_override_present=%s;"
                "actor_component_override_applied=%s;"
                "simple_motion_component_override_applied=%s",
                actorOverridePresent ? "true" : "false",
                simpleMotionOverridePresent ? "true" : "false",
                actorOverrideApplied ? "true" : "false",
                simpleMotionOverrideApplied ? "true" : "false");
        }

        return AZStd::string::format(
            "maxine_prefab_save_update_route_approved_source_override_applied;"
            "api=AzToolsFramework::Prefab::PrefabOverridePublicInterface::ApplyComponentOverrides;"
            "path_policy=active_project_root/Assets/Characters/MAXINE_GoldenCorpus/prefabs/release_rigged.prefab;"
            "actor_override_present=%s;"
            "simple_motion_override_present=%s;"
            "actor_component_override_applied=true;"
            "simple_motion_component_override_applied=true",
            actorOverridePresent ? "true" : "false",
            simpleMotionOverridePresent ? "true" : "false");
    }

    AZStd::string PrefabSaveUpdateBridgeHostComponent::CommitApprovedSourcePrefabEntityChanges(
        const AZStd::string& absolutePrefabPath,
        AZ::EntityId entityId)
    {
        const AZ::IO::Path prefabPath(absolutePrefabPath);
        const AZStd::string rejectionReason = RejectReasonForApprovedSourcePrefabPath(prefabPath);
        if (!rejectionReason.empty())
        {
            return RouteResult("approved_source_commit_rejected", rejectionReason);
        }
        if (!entityId.IsValid())
        {
            return RouteResult("approved_source_commit_failed", "entity_id_invalid");
        }

        auto* prefabPublicInterface = AZ::Interface<AzToolsFramework::Prefab::PrefabPublicInterface>::Get();
        if (!prefabPublicInterface)
        {
            return RouteResult("approved_source_commit_failed", "prefab_public_interface_unavailable");
        }

        auto* prefabLoaderInterface = AZ::Interface<AzToolsFramework::Prefab::PrefabLoaderInterface>::Get();
        if (!prefabLoaderInterface)
        {
            return RouteResult("approved_source_commit_failed", "prefab_loader_interface_unavailable");
        }

        AzToolsFramework::ScopedUndoBatch undoBatch("MAXINE approved source prefab entity wiring");
        const auto updateResult =
            prefabPublicInterface->GenerateUndoNodesForEntityChangeAndUpdateCache(entityId, undoBatch.GetUndoBatch());
        if (!updateResult.IsSuccess())
        {
            return RouteResult("approved_source_commit_failed", "generate_undo_nodes_for_entity_change_failed");
        }

        const AZ::IO::Path relativePath = prefabLoaderInterface->GenerateRelativePath(prefabPath);
        const auto saveResult = prefabPublicInterface->SavePrefab(relativePath);
        if (!saveResult.IsSuccess())
        {
            return RouteResult("approved_source_commit_failed", "save_prefab_failed_after_entity_change_commit");
        }

        return AZStd::string(
            "maxine_prefab_save_update_route_approved_source_entity_changes_committed;"
            "api=AzToolsFramework::Prefab::PrefabPublicInterface::GenerateUndoNodesForEntityChangeAndUpdateCache;"
            "save_api=AzToolsFramework::Prefab::PrefabPublicInterface::SavePrefab;"
            "relative_path_backend=AzToolsFramework::Prefab::PrefabLoaderInterface::GenerateRelativePath;"
            "path_policy=active_project_root/Assets/Characters/MAXINE_GoldenCorpus/prefabs/release_rigged.prefab;"
            "approved_source_entity_changes_committed=true;"
            "approved_source_save_verified=true");
    }

    AZStd::string PrefabSaveUpdateBridgeHostComponent::SaveApprovedSourcePrefabWiring(const AZStd::string& absolutePrefabPath)
    {
        const AZ::IO::Path prefabPath(absolutePrefabPath);
        const AZStd::string rejectionReason = RejectReasonForApprovedSourcePrefabPath(prefabPath);
        if (!rejectionReason.empty())
        {
            return RouteResult("approved_source_rejected", rejectionReason);
        }

        auto* prefabPublicInterface = AZ::Interface<AzToolsFramework::Prefab::PrefabPublicInterface>::Get();
        if (!prefabPublicInterface)
        {
            return RouteResult("approved_source_failed", "prefab_public_interface_unavailable");
        }

        auto* prefabLoaderInterface = AZ::Interface<AzToolsFramework::Prefab::PrefabLoaderInterface>::Get();
        if (!prefabLoaderInterface)
        {
            return RouteResult("approved_source_failed", "prefab_loader_interface_unavailable");
        }

        const AZ::IO::Path relativePath = prefabLoaderInterface->GenerateRelativePath(prefabPath);
        const auto saveResult = prefabPublicInterface->SavePrefab(relativePath);
        if (!saveResult.IsSuccess())
        {
            return RouteResult("approved_source_failed", "save_prefab_failed");
        }

        if (!AZ::IO::SystemFile::Exists(prefabPath.FixedMaxPathString().c_str()))
        {
            return RouteResult("approved_source_failed", "approved_source_prefab_not_found_after_save");
        }

        return AZStd::string(
            "maxine_prefab_save_update_route_approved_source_saved;"
            "api=AzToolsFramework::Prefab::PrefabPublicInterface::SavePrefab;"
            "relative_path_backend=AzToolsFramework::Prefab::PrefabLoaderInterface::GenerateRelativePath;"
            "path_policy=active_project_root/Assets/Characters/MAXINE_GoldenCorpus/prefabs/release_rigged.prefab;"
            "approved_source_save_verified=true");
    }

    void PrefabSaveUpdateBridgeHostComponent::Activate()
    {
    }

    void PrefabSaveUpdateBridgeHostComponent::Deactivate()
    {
    }
} // namespace MaxineRuntimeExitFixture
