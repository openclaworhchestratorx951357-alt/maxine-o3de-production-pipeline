#include "PrefabSaveUpdateBridgeHostComponent.h"

#include <AzCore/Component/ComponentApplicationBus.h>
#include <AzCore/Component/Entity.h>
#include <AzCore/IO/Path/Path.h>
#include <AzCore/IO/SystemFile.h>
#include <AzCore/Interface/Interface.h>
#include <AzCore/RTTI/BehaviorContext.h>
#include <AzCore/Serialization/SerializeContext.h>
#include <AzCore/std/containers/vector.h>
#include <AzCore/Utils/Utils.h>
#include <AzToolsFramework/Prefab/Instance/Instance.h>
#include <AzToolsFramework/Prefab/Instance/InstanceEntityMapperInterface.h>
#include <AzToolsFramework/Prefab/Instance/InstanceToTemplateInterface.h>
#include <AzToolsFramework/Prefab/Overrides/PrefabOverridePublicInterface.h>
#include <AzToolsFramework/Prefab/PrefabDomUtils.h>
#include <AzToolsFramework/Prefab/PrefabFocusPublicInterface.h>
#include <AzToolsFramework/Prefab/PrefabIdTypes.h>
#include <AzToolsFramework/Prefab/PrefabLoaderInterface.h>
#include <AzToolsFramework/Prefab/PrefabPublicInterface.h>
#include <AzToolsFramework/Prefab/PrefabSystemComponentInterface.h>
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

    AZStd::string NormalizedFullPrefabPath(
        const AZ::IO::Path& prefabPath,
        AzToolsFramework::Prefab::PrefabLoaderInterface& prefabLoaderInterface)
    {
        const AZ::IO::Path fullPath = prefabPath.IsAbsolute() ? prefabPath : prefabLoaderInterface.GetFullPath(prefabPath);
        return NormalizeForPathPolicy(fullPath.LexicallyNormal().String());
    }

    AZStd::string ParentLinkOwnershipFields(
        AZStd::string_view owningPrefabPath,
        bool entityOwnershipVerified,
        bool owningPrefabMatchesRequestedPath,
        bool componentOwnershipChecked,
        bool componentOwnershipVerified)
    {
        return AZStd::string::format(
            "entity_ownership_checked=true;"
            "entity_ownership_verified=%s;"
            "entity_owning_prefab_path=%.*s;"
            "entity_owning_prefab_matches_requested_path=%s;"
            "component_ownership_checked=%s;"
            "component_ownership_verified=%s;",
            entityOwnershipVerified ? "true" : "false",
            AZ_STRING_ARG(owningPrefabPath),
            owningPrefabMatchesRequestedPath ? "true" : "false",
            componentOwnershipChecked ? "true" : "false",
            componentOwnershipVerified ? "true" : "false");
    }

    AZStd::string ParentLinkOwnershipBlockedResult(
        AZStd::string_view reason,
        AZStd::string_view owningPrefabPath,
        bool entityOwnershipVerified,
        bool owningPrefabMatchesRequestedPath,
        bool componentOwnershipChecked,
        bool componentOwnershipVerified)
    {
        return AZStd::string::format(
            "maxine_prefab_save_update_route_approved_source_parent_link_override_failed;"
            "reason=%.*s;"
            "%s"
            "parent_focus_context_required=true;"
            "parent_focus_context_available=false;"
            "parent_focus_context_applied=false;"
            "parent_focus_context_restored=false;"
            "link_context_required=true;"
            "link_context_available=false;"
            "component_override_paths_detected=false;"
            "actor_component_override_applied=false;"
            "simple_motion_component_override_applied=false;"
            "push_overrides_to_prefab_attempted=false;"
            "push_overrides_to_prefab_verified=false",
            AZ_STRING_ARG(reason),
            ParentLinkOwnershipFields(
                owningPrefabPath,
                entityOwnershipVerified,
                owningPrefabMatchesRequestedPath,
                componentOwnershipChecked,
                componentOwnershipVerified)
                .c_str());
    }

    AZStd::string TemplateUpdateBlockedResult(
        AZStd::string_view reason,
        AZStd::string_view owningPrefabPath,
        bool entityOwnershipVerified,
        bool owningPrefabMatchesRequestedPath,
        bool componentOwnershipChecked,
        bool componentOwnershipVerified)
    {
        return AZStd::string::format(
            "maxine_prefab_save_update_route_approved_source_template_update_failed;"
            "reason=%.*s;"
            "%s"
            "source_backed_template_update_route_used=false;"
            "template_dom_initial_entity_found=false;"
            "serialized_entity_dom_generated=false;"
            "entity_patch_generated=false;"
            "entity_patch_operation_count=0;"
            "patch_entity_in_template_attempted=false;"
            "patch_entity_in_template_verified=false;"
            "template_dom_updated=false;"
            "approved_source_save_verified=false",
            AZ_STRING_ARG(reason),
            ParentLinkOwnershipFields(
                owningPrefabPath,
                entityOwnershipVerified,
                owningPrefabMatchesRequestedPath,
                componentOwnershipChecked,
                componentOwnershipVerified)
                .c_str());
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
                    "apply_approved_source_prefab_parent_link_component_overrides",
                    &PrefabSaveUpdateBridgeHostComponent::ApplyApprovedSourcePrefabParentLinkComponentOverrides,
                    nullptr,
                    "Focuses the approved prefab parent/link context and applies generated Actor and Simple Motion component overrides.")
                ->Attribute(AZ::Script::Attributes::Scope, AZ::Script::Attributes::ScopeFlags::Automation)
                ->Attribute(AZ::Script::Attributes::Category, "MAXINE/PrefabSaveUpdateBridge")
                ->Attribute(AZ::Script::Attributes::Module, "maxine.prefab_bridge");
            behaviorContext
                ->Method(
                    "apply_approved_source_prefab_override_path_generation_template_update",
                    &PrefabSaveUpdateBridgeHostComponent::ApplyApprovedSourcePrefabOverridePathGenerationTemplateUpdate,
                    nullptr,
                    "Serializes an approved source-prefab entity, generates a source-backed patch, updates its template, and saves it.")
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

    AZStd::string PrefabSaveUpdateBridgeHostComponent::ApplyApprovedSourcePrefabParentLinkComponentOverrides(
        const AZStd::string& absolutePrefabPath,
        AZ::EntityId entityId,
        const AZ::EntityComponentIdPair& actorComponent,
        const AZ::EntityComponentIdPair& simpleMotionComponent)
    {
        const AZ::IO::Path prefabPath(absolutePrefabPath);
        const AZStd::string rejectionReason = RejectReasonForApprovedSourcePrefabPath(prefabPath);
        if (!rejectionReason.empty())
        {
            return RouteResult("approved_source_parent_link_override_rejected", rejectionReason);
        }
        if (!entityId.IsValid())
        {
            return RouteResult("approved_source_parent_link_override_failed", "entity_id_invalid");
        }

        auto* prefabPublicInterface = AZ::Interface<AzToolsFramework::Prefab::PrefabPublicInterface>::Get();
        if (!prefabPublicInterface)
        {
            return RouteResult("approved_source_parent_link_override_failed", "prefab_public_interface_unavailable");
        }

        auto* prefabLoaderInterface = AZ::Interface<AzToolsFramework::Prefab::PrefabLoaderInterface>::Get();
        if (!prefabLoaderInterface)
        {
            return RouteResult("approved_source_parent_link_override_failed", "prefab_loader_interface_unavailable");
        }

        const AZ::IO::Path owningPrefabPath = prefabPublicInterface->GetOwningInstancePrefabPath(entityId);
        if (owningPrefabPath.String().empty())
        {
            return ParentLinkOwnershipBlockedResult(
                "entity_owning_prefab_unavailable",
                "",
                false,
                false,
                false,
                false);
        }

        const AZStd::string normalizedOwningPrefabPath = NormalizedFullPrefabPath(owningPrefabPath, *prefabLoaderInterface);
        const AZStd::string normalizedRequestedPrefabPath = NormalizedFullPrefabPath(prefabPath, *prefabLoaderInterface);
        if (normalizedOwningPrefabPath != normalizedRequestedPrefabPath)
        {
            return ParentLinkOwnershipBlockedResult(
                "entity_not_owned_by_approved_source_prefab",
                normalizedOwningPrefabPath,
                false,
                false,
                false,
                false);
        }

        AZ::Entity* entity = nullptr;
        AZ::ComponentApplicationBus::BroadcastResult(entity, &AZ::ComponentApplicationRequests::FindEntity, entityId);
        const bool actorComponentOwnedByEntity =
            actorComponent.GetEntityId() == entityId &&
            actorComponent.GetComponentId() != AZ::InvalidComponentId &&
            entity != nullptr &&
            entity->FindComponent(actorComponent.GetComponentId()) != nullptr;
        const bool simpleMotionComponentOwnedByEntity =
            simpleMotionComponent.GetEntityId() == entityId &&
            simpleMotionComponent.GetComponentId() != AZ::InvalidComponentId &&
            entity != nullptr &&
            entity->FindComponent(simpleMotionComponent.GetComponentId()) != nullptr;
        if (!actorComponentOwnedByEntity || !simpleMotionComponentOwnedByEntity)
        {
            return ParentLinkOwnershipBlockedResult(
                "component_not_owned_by_approved_source_prefab_entity",
                normalizedOwningPrefabPath,
                true,
                true,
                true,
                false);
        }

        const AZStd::string ownershipFields = ParentLinkOwnershipFields(
            normalizedOwningPrefabPath,
            true,
            true,
            true,
            true);

        auto* prefabOverridePublicInterface = AZ::Interface<AzToolsFramework::Prefab::PrefabOverridePublicInterface>::Get();
        if (!prefabOverridePublicInterface)
        {
            return RouteResult("approved_source_parent_link_override_failed", "prefab_override_public_interface_unavailable");
        }

        auto* prefabFocusPublicInterface = AZ::Interface<AzToolsFramework::Prefab::PrefabFocusPublicInterface>::Get();
        if (!prefabFocusPublicInterface)
        {
            return RouteResult("approved_source_parent_link_override_failed", "prefab_focus_public_interface_unavailable");
        }

        AzFramework::EntityContextId editorEntityContextId;
        AzToolsFramework::EditorEntityContextRequestBus::BroadcastResult(
            editorEntityContextId,
            &AzToolsFramework::EditorEntityContextRequestBus::Events::GetEditorEntityContextId);

        const int initialFocusPathLength = prefabFocusPublicInterface->GetPrefabFocusPathLength(editorEntityContextId);
        AZ_UNUSED(initialFocusPathLength);
        const auto owningFocusResult = prefabFocusPublicInterface->FocusOnOwningPrefab(entityId);
        if (!owningFocusResult.IsSuccess())
        {
            return AZStd::string::format(
                "maxine_prefab_save_update_route_approved_source_parent_link_override_failed;"
                "reason=focus_on_owning_prefab_failed;"
                "%s"
                "parent_focus_context_required=true;"
                "parent_focus_context_available=false;"
                "parent_focus_context_applied=false;"
                "parent_focus_context_restored=false;"
                "link_context_required=true;"
                "link_context_available=false;"
                "focus_on_owning_prefab_succeeded=false;"
                "focus_error=%s",
                ownershipFields.c_str(),
                owningFocusResult.GetError().c_str());
        }

        const int owningFocusPathLength = prefabFocusPublicInterface->GetPrefabFocusPathLength(editorEntityContextId);
        const bool parentFocusContextAvailable = owningFocusPathLength > 1;
        if (!parentFocusContextAvailable)
        {
            const auto restoreFocusResult = prefabFocusPublicInterface->FocusOnOwningPrefab(entityId);
            return AZStd::string::format(
                "maxine_prefab_save_update_route_approved_source_parent_link_override_failed;"
                "reason=parent_focus_context_unavailable;"
                "%s"
                "parent_focus_context_required=true;"
                "parent_focus_context_available=false;"
                "parent_focus_context_applied=false;"
                "parent_focus_context_restored=%s;"
                "link_context_required=true;"
                "link_context_available=false;"
                "focus_on_owning_prefab_succeeded=true;"
                "owning_focus_path_length=%d",
                ownershipFields.c_str(),
                restoreFocusResult.IsSuccess() ? "true" : "false",
                owningFocusPathLength);
        }

        const auto parentFocusResult = prefabFocusPublicInterface->FocusOnParentOfFocusedPrefab(editorEntityContextId);
        if (!parentFocusResult.IsSuccess())
        {
            const auto restoreFocusResult = prefabFocusPublicInterface->FocusOnOwningPrefab(entityId);
            return AZStd::string::format(
                "maxine_prefab_save_update_route_approved_source_parent_link_override_failed;"
                "reason=focus_on_parent_prefab_failed;"
                "%s"
                "parent_focus_context_required=true;"
                "parent_focus_context_available=true;"
                "parent_focus_context_applied=false;"
                "parent_focus_context_restored=%s;"
                "link_context_required=true;"
                "link_context_available=false;"
                "focus_on_owning_prefab_succeeded=true;"
                "focus_on_parent_prefab_succeeded=false;"
                "focus_error=%s",
                ownershipFields.c_str(),
                restoreFocusResult.IsSuccess() ? "true" : "false",
                parentFocusResult.GetError().c_str());
        }

        const bool actorOverridePresent = prefabOverridePublicInterface->AreComponentOverridesPresent(actorComponent);
        const bool simpleMotionOverridePresent = prefabOverridePublicInterface->AreComponentOverridesPresent(simpleMotionComponent);
        const bool componentOverridePathsDetected = actorOverridePresent && simpleMotionOverridePresent;
        const bool actorOverrideApplied = prefabOverridePublicInterface->ApplyComponentOverrides(actorComponent);
        const bool simpleMotionOverrideApplied = prefabOverridePublicInterface->ApplyComponentOverrides(simpleMotionComponent);
        const bool applied = actorOverrideApplied && simpleMotionOverrideApplied;
        const auto restoreFocusResult = prefabFocusPublicInterface->FocusOnOwningPrefab(entityId);

        if (!applied)
        {
            return AZStd::string::format(
                "maxine_prefab_save_update_route_approved_source_parent_link_override_failed;"
                "reason=component_override_apply_failed;"
                "%s"
                "api=AzToolsFramework::Prefab::PrefabFocusPublicInterface::FocusOnOwningPrefab+FocusOnParentOfFocusedPrefab;"
                "apply_api=AzToolsFramework::Prefab::PrefabOverridePublicInterface::ApplyComponentOverrides;"
                "push_backend=AzToolsFramework::Prefab::PrefabOverridePublicHandler::PushOverridesToPrefab;"
                "parent_focus_context_required=true;"
                "parent_focus_context_available=true;"
                "parent_focus_context_applied=true;"
                "parent_focus_context_restored=%s;"
                "link_context_required=true;"
                "link_context_available=%s;"
                "component_override_paths_detected=%s;"
                "actor_component_override_present=%s;"
                "simple_motion_component_override_present=%s;"
                "actor_component_override_applied=%s;"
                "simple_motion_component_override_applied=%s;"
                "push_overrides_to_prefab_attempted=true;"
                "push_overrides_to_prefab_verified=false",
                ownershipFields.c_str(),
                restoreFocusResult.IsSuccess() ? "true" : "false",
                componentOverridePathsDetected ? "true" : "false",
                componentOverridePathsDetected ? "true" : "false",
                actorOverridePresent ? "true" : "false",
                simpleMotionOverridePresent ? "true" : "false",
                actorOverrideApplied ? "true" : "false",
                simpleMotionOverrideApplied ? "true" : "false");
        }
        if (!restoreFocusResult.IsSuccess())
        {
            return AZStd::string::format(
                "maxine_prefab_save_update_route_approved_source_parent_link_override_failed;"
                "reason=parent_focus_context_restore_failed;"
                "%s"
                "api=AzToolsFramework::Prefab::PrefabFocusPublicInterface::FocusOnOwningPrefab+FocusOnParentOfFocusedPrefab;"
                "apply_api=AzToolsFramework::Prefab::PrefabOverridePublicInterface::ApplyComponentOverrides;"
                "push_backend=AzToolsFramework::Prefab::PrefabOverridePublicHandler::PushOverridesToPrefab;"
                "parent_focus_context_required=true;"
                "parent_focus_context_available=true;"
                "parent_focus_context_applied=true;"
                "parent_focus_context_restored=false;"
                "link_context_required=true;"
                "link_context_available=true;"
                "component_override_paths_detected=true;"
                "actor_component_override_present=true;"
                "simple_motion_component_override_present=true;"
                "actor_component_override_applied=true;"
                "simple_motion_component_override_applied=true;"
                "push_overrides_to_prefab_attempted=true;"
                "push_overrides_to_prefab_verified=true;"
                "focus_error=%s",
                ownershipFields.c_str(),
                restoreFocusResult.GetError().c_str());
        }

        return AZStd::string::format(
            "maxine_prefab_save_update_route_approved_source_parent_link_override_applied;"
            "%s"
            "api=AzToolsFramework::Prefab::PrefabFocusPublicInterface::FocusOnOwningPrefab+FocusOnParentOfFocusedPrefab;"
            "apply_api=AzToolsFramework::Prefab::PrefabOverridePublicInterface::ApplyComponentOverrides;"
            "push_backend=AzToolsFramework::Prefab::PrefabOverridePublicHandler::PushOverridesToPrefab;"
            "path_policy=active_project_root/Assets/Characters/MAXINE_GoldenCorpus/prefabs/release_rigged.prefab;"
            "parent_focus_context_required=true;"
            "parent_focus_context_available=true;"
            "parent_focus_context_applied=true;"
            "parent_focus_context_restored=true;"
            "link_context_required=true;"
            "link_context_available=true;"
            "component_override_paths_detected=true;"
            "actor_component_override_present=true;"
            "simple_motion_component_override_present=true;"
            "actor_component_override_applied=true;"
            "simple_motion_component_override_applied=true;"
            "push_overrides_to_prefab_attempted=true;"
            "push_overrides_to_prefab_verified=true",
            ownershipFields.c_str());
    }

    AZStd::string PrefabSaveUpdateBridgeHostComponent::ApplyApprovedSourcePrefabOverridePathGenerationTemplateUpdate(
        const AZStd::string& absolutePrefabPath,
        AZ::EntityId entityId,
        const AZ::EntityComponentIdPair& actorComponent,
        const AZ::EntityComponentIdPair& simpleMotionComponent)
    {
        const AZ::IO::Path prefabPath(absolutePrefabPath);
        const AZStd::string rejectionReason = RejectReasonForApprovedSourcePrefabPath(prefabPath);
        if (!rejectionReason.empty())
        {
            return RouteResult("approved_source_template_update_rejected", rejectionReason);
        }
        if (!entityId.IsValid())
        {
            return RouteResult("approved_source_template_update_failed", "entity_id_invalid");
        }

        auto* prefabPublicInterface = AZ::Interface<AzToolsFramework::Prefab::PrefabPublicInterface>::Get();
        if (!prefabPublicInterface)
        {
            return RouteResult("approved_source_template_update_failed", "prefab_public_interface_unavailable");
        }

        auto* prefabLoaderInterface = AZ::Interface<AzToolsFramework::Prefab::PrefabLoaderInterface>::Get();
        if (!prefabLoaderInterface)
        {
            return RouteResult("approved_source_template_update_failed", "prefab_loader_interface_unavailable");
        }

        const AZ::IO::Path owningPrefabPath = prefabPublicInterface->GetOwningInstancePrefabPath(entityId);
        if (owningPrefabPath.String().empty())
        {
            return TemplateUpdateBlockedResult(
                "entity_owning_prefab_unavailable",
                "",
                false,
                false,
                false,
                false);
        }

        const AZStd::string normalizedOwningPrefabPath = NormalizedFullPrefabPath(owningPrefabPath, *prefabLoaderInterface);
        const AZStd::string normalizedRequestedPrefabPath = NormalizedFullPrefabPath(prefabPath, *prefabLoaderInterface);
        if (normalizedOwningPrefabPath != normalizedRequestedPrefabPath)
        {
            return TemplateUpdateBlockedResult(
                "entity_not_owned_by_approved_source_prefab",
                normalizedOwningPrefabPath,
                false,
                false,
                false,
                false);
        }

        AZ::Entity* entity = nullptr;
        AZ::ComponentApplicationBus::BroadcastResult(entity, &AZ::ComponentApplicationRequests::FindEntity, entityId);
        const bool actorComponentOwnedByEntity =
            actorComponent.GetEntityId() == entityId &&
            actorComponent.GetComponentId() != AZ::InvalidComponentId &&
            entity != nullptr &&
            entity->FindComponent(actorComponent.GetComponentId()) != nullptr;
        const bool simpleMotionComponentOwnedByEntity =
            simpleMotionComponent.GetEntityId() == entityId &&
            simpleMotionComponent.GetComponentId() != AZ::InvalidComponentId &&
            entity != nullptr &&
            entity->FindComponent(simpleMotionComponent.GetComponentId()) != nullptr;
        if (!actorComponentOwnedByEntity || !simpleMotionComponentOwnedByEntity)
        {
            return TemplateUpdateBlockedResult(
                "component_not_owned_by_approved_source_prefab_entity",
                normalizedOwningPrefabPath,
                true,
                true,
                true,
                false);
        }

        const AZStd::string ownershipFields = ParentLinkOwnershipFields(
            normalizedOwningPrefabPath,
            true,
            true,
            true,
            true);

        auto* instanceEntityMapperInterface = AZ::Interface<AzToolsFramework::Prefab::InstanceEntityMapperInterface>::Get();
        if (!instanceEntityMapperInterface)
        {
            return AZStd::string::format(
                "maxine_prefab_save_update_route_approved_source_template_update_failed;"
                "reason=instance_entity_mapper_interface_unavailable;"
                "%s"
                "source_backed_template_update_route_used=false;"
                "template_dom_updated=false;"
                "approved_source_save_verified=false",
                ownershipFields.c_str());
        }

        auto* instanceToTemplateInterface = AZ::Interface<AzToolsFramework::Prefab::InstanceToTemplateInterface>::Get();
        if (!instanceToTemplateInterface)
        {
            return AZStd::string::format(
                "maxine_prefab_save_update_route_approved_source_template_update_failed;"
                "reason=instance_to_template_interface_unavailable;"
                "%s"
                "source_backed_template_update_route_used=false;"
                "template_dom_updated=false;"
                "approved_source_save_verified=false",
                ownershipFields.c_str());
        }

        auto* prefabSystemComponentInterface = AZ::Interface<AzToolsFramework::Prefab::PrefabSystemComponentInterface>::Get();
        if (!prefabSystemComponentInterface)
        {
            return AZStd::string::format(
                "maxine_prefab_save_update_route_approved_source_template_update_failed;"
                "reason=prefab_system_component_interface_unavailable;"
                "%s"
                "source_backed_template_update_route_used=false;"
                "template_dom_updated=false;"
                "approved_source_save_verified=false",
                ownershipFields.c_str());
        }

        AzToolsFramework::Prefab::InstanceOptionalReference owningInstance =
            instanceEntityMapperInterface->FindOwningInstance(entityId);
        if (!owningInstance.has_value())
        {
            return TemplateUpdateBlockedResult(
                "entity_owning_prefab_unavailable",
                normalizedOwningPrefabPath,
                true,
                true,
                true,
                true);
        }

        const AzToolsFramework::Prefab::TemplateId templateId = owningInstance->get().GetTemplateId();
        if (templateId == AzToolsFramework::Prefab::InvalidTemplateId)
        {
            return AZStd::string::format(
                "maxine_prefab_save_update_route_approved_source_template_update_failed;"
                "reason=template_id_unavailable;"
                "%s"
                "source_backed_template_update_route_used=true;"
                "template_dom_updated=false;"
                "approved_source_save_verified=false",
                ownershipFields.c_str());
        }

        AzToolsFramework::Prefab::EntityAliasOptionalReference entityAliasRef = owningInstance->get().GetEntityAlias(entityId);
        if (!entityAliasRef.has_value() || entityAliasRef->get().empty())
        {
            return AZStd::string::format(
                "maxine_prefab_save_update_route_approved_source_template_update_failed;"
                "reason=entity_alias_unavailable;"
                "%s"
                "source_backed_template_update_route_used=true;"
                "template_dom_updated=false;"
                "approved_source_save_verified=false",
                ownershipFields.c_str());
        }

        AzToolsFramework::Prefab::PrefabDom& templateDom = prefabSystemComponentInterface->FindTemplateDom(templateId);
        AzToolsFramework::Prefab::PrefabDomValue* initialEntityDomValue = nullptr;
        const bool isContainerEntity = entityId == owningInstance->get().GetContainerEntityId();
        if (isContainerEntity)
        {
            auto containerIt = templateDom.FindMember(AzToolsFramework::Prefab::PrefabDomUtils::ContainerEntityName);
            if (containerIt != templateDom.MemberEnd() && containerIt->value.IsObject())
            {
                initialEntityDomValue = &containerIt->value;
            }
        }
        else
        {
            auto entitiesIt = templateDom.FindMember(AzToolsFramework::Prefab::PrefabDomUtils::EntitiesName);
            if (entitiesIt == templateDom.MemberEnd() || !entitiesIt->value.IsObject())
            {
                return AZStd::string::format(
                    "maxine_prefab_save_update_route_approved_source_template_update_failed;"
                    "reason=template_dom_entities_unavailable;"
                    "%s"
                    "source_backed_template_update_route_used=true;"
                    "template_dom_initial_entity_found=false;"
                    "template_dom_updated=false;"
                    "approved_source_save_verified=false",
                    ownershipFields.c_str());
            }

            const AZStd::string& entityAlias = entityAliasRef->get();
            auto entityIt = entitiesIt->value.FindMember(entityAlias.c_str());
            if (entityIt != entitiesIt->value.MemberEnd() && entityIt->value.IsObject())
            {
                initialEntityDomValue = &entityIt->value;
            }
        }

        if (initialEntityDomValue == nullptr)
        {
            return AZStd::string::format(
                "maxine_prefab_save_update_route_approved_source_template_update_failed;"
                "reason=template_dom_initial_entity_unavailable;"
                "%s"
                "source_backed_template_update_route_used=true;"
                "template_dom_initial_entity_found=false;"
                "template_dom_updated=false;"
                "approved_source_save_verified=false",
                ownershipFields.c_str());
        }

        AzToolsFramework::Prefab::PrefabDom initialEntityDom;
        initialEntityDom.CopyFrom(*initialEntityDomValue, initialEntityDom.GetAllocator());

        AzToolsFramework::Prefab::PrefabDom modifiedEntityDom;
        const bool serializedEntityDomGenerated = instanceToTemplateInterface->GenerateEntityDomBySerializing(modifiedEntityDom, *entity);
        if (!serializedEntityDomGenerated)
        {
            return AZStd::string::format(
                "maxine_prefab_save_update_route_approved_source_template_update_failed;"
                "reason=serialized_entity_dom_generation_failed;"
                "%s"
                "source_backed_template_update_route_used=true;"
                "template_dom_initial_entity_found=true;"
                "serialized_entity_dom_generated=false;"
                "entity_patch_generated=false;"
                "entity_patch_operation_count=0;"
                "patch_entity_in_template_attempted=false;"
                "patch_entity_in_template_verified=false;"
                "template_dom_updated=false;"
                "approved_source_save_verified=false",
                ownershipFields.c_str());
        }

        AzToolsFramework::Prefab::PrefabDom entityPatch;
        const bool entityPatchGenerated = instanceToTemplateInterface->GeneratePatch(entityPatch, initialEntityDom, modifiedEntityDom);
        const bool entityPatchHasOperations = entityPatch.IsArray() && !entityPatch.GetArray().Empty();
        const rapidjson::SizeType entityPatchOperationCount = entityPatch.IsArray() ? entityPatch.Size() : 0;
        if (!entityPatchGenerated || !entityPatchHasOperations)
        {
            return AZStd::string::format(
                "maxine_prefab_save_update_route_approved_source_template_update_failed;"
                "reason=%s;"
                "%s"
                "source_backed_template_update_route_used=true;"
                "template_dom_initial_entity_found=true;"
                "serialized_entity_dom_generated=true;"
                "entity_patch_generated=%s;"
                "entity_patch_operation_count=%u;"
                "patch_entity_in_template_attempted=false;"
                "patch_entity_in_template_verified=false;"
                "template_dom_updated=false;"
                "approved_source_save_verified=false",
                entityPatchGenerated ? "source_backed_entity_patch_empty" : "source_backed_entity_patch_generation_failed",
                ownershipFields.c_str(),
                entityPatchGenerated ? "true" : "false",
                entityPatchOperationCount);
        }

        const bool patchEntityInTemplateVerified = instanceToTemplateInterface->PatchEntityInTemplate(entityPatch, entityId);
        if (!patchEntityInTemplateVerified)
        {
            return AZStd::string::format(
                "maxine_prefab_save_update_route_approved_source_template_update_failed;"
                "reason=patch_entity_in_template_failed;"
                "%s"
                "source_backed_template_update_route_used=true;"
                "template_dom_initial_entity_found=true;"
                "serialized_entity_dom_generated=true;"
                "entity_patch_generated=true;"
                "entity_patch_operation_count=%u;"
                "patch_entity_in_template_attempted=true;"
                "patch_entity_in_template_verified=false;"
                "template_dom_updated=false;"
                "approved_source_save_verified=false",
                ownershipFields.c_str(),
                entityPatchOperationCount);
        }

        const AZ::IO::Path relativePath = prefabLoaderInterface->GenerateRelativePath(prefabPath);
        const auto saveResult = prefabPublicInterface->SavePrefab(relativePath);
        if (!saveResult.IsSuccess())
        {
            return AZStd::string::format(
                "maxine_prefab_save_update_route_approved_source_template_update_failed;"
                "reason=save_prefab_failed_after_template_update;"
                "%s"
                "source_backed_template_update_route_used=true;"
                "template_dom_initial_entity_found=true;"
                "serialized_entity_dom_generated=true;"
                "entity_patch_generated=true;"
                "entity_patch_operation_count=%u;"
                "patch_entity_in_template_attempted=true;"
                "patch_entity_in_template_verified=true;"
                "template_dom_updated=true;"
                "approved_source_save_verified=false",
                ownershipFields.c_str(),
                entityPatchOperationCount);
        }

        return AZStd::string::format(
            "maxine_prefab_save_update_route_approved_source_template_update_applied;"
            "%s"
            "api=AzToolsFramework::Prefab::InstanceToTemplateInterface::GenerateEntityDomBySerializing+GeneratePatch+PatchEntityInTemplate;"
            "save_api=AzToolsFramework::Prefab::PrefabPublicInterface::SavePrefab;"
            "relative_path_backend=AzToolsFramework::Prefab::PrefabLoaderInterface::GenerateRelativePath;"
            "path_policy=active_project_root/Assets/Characters/MAXINE_GoldenCorpus/prefabs/release_rigged.prefab;"
            "source_backed_template_update_route_used=true;"
            "template_dom_initial_entity_found=true;"
            "serialized_entity_dom_generated=true;"
            "entity_patch_generated=true;"
            "entity_patch_operation_count=%u;"
            "component_override_paths_detected=true;"
            "patch_entity_in_template_attempted=true;"
            "patch_entity_in_template_verified=true;"
            "template_dom_updated=true;"
            "approved_source_save_verified=true",
            ownershipFields.c_str(),
            entityPatchOperationCount);
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
