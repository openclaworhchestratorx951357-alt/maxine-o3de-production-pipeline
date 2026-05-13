#include "PrefabSaveUpdateBridgeHostComponent.h"

#include <AzCore/RTTI/BehaviorContext.h>
#include <AzCore/Serialization/SerializeContext.h>
#include <AzToolsFramework/Prefab/PrefabPublicInterface.h>

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
            "save_route_exposed=false;"
            "scratch_save_verified=false");
    }

    void PrefabSaveUpdateBridgeHostComponent::Activate()
    {
    }

    void PrefabSaveUpdateBridgeHostComponent::Deactivate()
    {
    }
} // namespace MaxineRuntimeExitFixture
