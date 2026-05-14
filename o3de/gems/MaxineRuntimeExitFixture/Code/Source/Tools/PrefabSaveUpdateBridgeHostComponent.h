#pragma once

#include <AzCore/Component/Component.h>
#include <AzCore/Component/EntityId.h>
#include <AzCore/std/string/string.h>

namespace MaxineRuntimeExitFixture
{
    class PrefabSaveUpdateBridgeHostComponent
        : public AZ::Component
    {
    public:
        AZ_COMPONENT_DECL(PrefabSaveUpdateBridgeHostComponent);

        static void Reflect(AZ::ReflectContext* context);
        static void GetProvidedServices(AZ::ComponentDescriptor::DependencyArrayType& provided);
        static void GetIncompatibleServices(AZ::ComponentDescriptor::DependencyArrayType& incompatible);
        static void GetRequiredServices(AZ::ComponentDescriptor::DependencyArrayType& required);
        static void GetDependentServices(AZ::ComponentDescriptor::DependencyArrayType& dependent);
        static AZStd::string GetPrefabSaveUpdateBridgeHostStatus();
        static AZStd::string SavePrefabUpdateScratchProbe(const AZStd::string& absolutePrefabPath);
        static AZStd::string ApplyApprovedSourcePrefabComponentOverrides(
            const AZStd::string& absolutePrefabPath,
            const AZ::EntityComponentIdPair& actorComponent,
            const AZ::EntityComponentIdPair& simpleMotionComponent);
        static AZStd::string ApplyApprovedSourcePrefabParentLinkComponentOverrides(
            const AZStd::string& absolutePrefabPath,
            AZ::EntityId entityId,
            const AZ::EntityComponentIdPair& actorComponent,
            const AZ::EntityComponentIdPair& simpleMotionComponent);
        static AZStd::string ApplyApprovedSourcePrefabOverridePathGenerationTemplateUpdate(
            const AZStd::string& absolutePrefabPath,
            AZ::EntityId entityId,
            const AZ::EntityComponentIdPair& actorComponent,
            const AZ::EntityComponentIdPair& simpleMotionComponent);
        static AZStd::string CommitApprovedSourcePrefabEntityChanges(
            const AZStd::string& absolutePrefabPath,
            AZ::EntityId entityId);
        static AZStd::string SaveApprovedSourcePrefabWiring(const AZStd::string& absolutePrefabPath);

        void Activate() override;
        void Deactivate() override;
    };
} // namespace MaxineRuntimeExitFixture
