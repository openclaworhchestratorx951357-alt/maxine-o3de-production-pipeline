#include "PrefabSaveUpdateBridgeHostComponent.h"

#include <AzCore/IO/Path/Path.h>
#include <AzCore/IO/SystemFile.h>
#include <AzCore/Interface/Interface.h>
#include <AzCore/RTTI/BehaviorContext.h>
#include <AzCore/Serialization/SerializeContext.h>
#include <AzCore/std/containers/vector.h>
#include <AzCore/Utils/Utils.h>
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

    void PrefabSaveUpdateBridgeHostComponent::Activate()
    {
    }

    void PrefabSaveUpdateBridgeHostComponent::Deactivate()
    {
    }
} // namespace MaxineRuntimeExitFixture
