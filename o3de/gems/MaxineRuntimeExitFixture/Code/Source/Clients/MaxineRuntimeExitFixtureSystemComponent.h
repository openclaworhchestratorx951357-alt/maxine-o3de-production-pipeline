#pragma once

#include <AzCore/Component/Component.h>
#include <AzCore/Component/TickBus.h>
#include <AzCore/Asset/AssetCommon.h>
#include <AzCore/std/string/string.h>
#include <AzCore/std/containers/vector.h>
#include <AzCore/std/parallel/mutex.h>
#include <AzFramework/Spawnable/SpawnableEntitiesInterface.h>

namespace MaxineRuntimeExitFixture
{
    class MaxineRuntimeExitFixtureSystemComponent
        : public AZ::Component
        , public AZ::TickBus::Handler
    {
    public:
        AZ_COMPONENT_DECL(MaxineRuntimeExitFixtureSystemComponent);

        static void Reflect(AZ::ReflectContext* context);
        static void GetProvidedServices(AZ::ComponentDescriptor::DependencyArrayType& provided);
        static void GetIncompatibleServices(AZ::ComponentDescriptor::DependencyArrayType& incompatible);
        static void GetRequiredServices(AZ::ComponentDescriptor::DependencyArrayType& required);
        static void GetDependentServices(AZ::ComponentDescriptor::DependencyArrayType& dependent);

        void Activate() override;
        void Deactivate() override;
        void OnTick(float deltaTime, AZ::ScriptTimePoint time) override;

    private:
        struct ProductLoadProbeEntry
        {
            AZStd::string m_kind;
            AZStd::string m_productPath;
            AZStd::string m_catalogPath;
            AZStd::string m_expectedCategory;
            AZ::Data::AssetId m_assetId;
            AZ::Data::AssetType m_assetType;
            AZ::Data::Asset<AZ::Data::AssetData> m_asset;
            bool m_resolved = false;
            bool m_loadRequested = false;
            bool m_ready = false;
            bool m_error = false;
            bool m_timeout = false;
            bool m_released = false;
        };

        void ConfigureProductLoadProbe();
        void StartProductLoadProbe();
        void PollProductLoadProbe();
        void CompleteProductLoadProbe(const char* status);
        void ReleaseProductLoadProbeAssets();
        void ConfigureCharacterSpawnInstantiationProbe();
        void StartCharacterSpawnInstantiationProbe();
        void PollCharacterSpawnInstantiationProbe();
        bool PollCharacterAnimationPlaybackExecutionProbe();
        void ConfigureCharacterAnimationPlaybackExecutionProbe();
        void ResetCharacterAnimationPlaybackExecutionProbe();
        void CompleteCharacterSpawnInstantiationProbe(const char* status);
        void ReleaseCharacterSpawnInstantiationProbe();

        bool m_enabled = false;
        AZ::u64 m_exitAfterTicks = 0;
        AZ::u64 m_ticksObserved = 0;
        bool m_productLoadProbeEnabled = false;
        bool m_productLoadProbeStarted = false;
        bool m_productLoadProbeComplete = false;
        bool m_requireAllProductsReady = true;
        AZ::u64 m_productLoadTimeoutTicks = 0;
        AZ::u64 m_productLoadStartTick = 0;
        AZStd::vector<ProductLoadProbeEntry> m_productLoadProducts;
        bool m_characterSpawnProbeEnabled = false;
        bool m_characterSpawnProbeStarted = false;
        bool m_characterSpawnProbeComplete = false;
        bool m_characterSpawnLoadRequested = false;
        bool m_characterSpawnReady = false;
        bool m_characterSpawnRequestIssued = false;
        bool m_characterSpawnCompletionObserved = false;
        bool m_characterSpawnCleanupRequested = false;
        bool m_characterSpawnCleanupComplete = false;
        bool m_characterSpawnRequirePositiveEntityCount = true;
        bool m_characterSpawnCleanupSpawnedEntities = true;
        bool m_characterSpawnError = false;
        bool m_characterSpawnTimeout = false;
        AZ::u64 m_characterSpawnTimeoutTicks = 0;
        AZ::u64 m_characterSpawnStartTick = 0;
        AZStd::string m_characterSpawnProductPath;
        AZStd::string m_characterSpawnCatalogPath;
        AZStd::string m_characterSpawnExpectedAssetId;
        AZStd::string m_characterSpawnExpectedAssetType;
        AZ::Data::AssetId m_characterSpawnAssetId;
        AZ::Data::AssetType m_characterSpawnAssetType;
        AZ::Data::Asset<AzFramework::Spawnable> m_characterSpawnAsset;
        AzFramework::EntitySpawnTicket m_characterSpawnTicket;
        AZStd::vector<AZ::EntityId> m_characterSpawnedRawEntityIds;
        AZStd::vector<AZStd::string> m_characterSpawnedEntityIds;
        AZStd::vector<AZStd::string> m_characterSpawnedEntityNames;
        AZStd::vector<AZStd::string> m_characterSpawnedEntityComponentInventory;
        bool m_characterAnimationPlaybackProbeEnabled = false;
        bool m_characterAnimationPlaybackRequestAttempted = false;
        bool m_characterAnimationPlaybackRequestSucceeded = false;
        bool m_characterAnimationPlaybackStarted = false;
        bool m_characterAnimationPlaybackObserved = false;
        bool m_characterAnimationPlaybackTimeAdvanced = false;
        bool m_characterAnimationPlaybackActiveStateObserved = false;
        bool m_characterAnimationPlaybackActorInstanceAvailableBefore = false;
        bool m_characterAnimationPlaybackMotionInstanceAvailableBefore = false;
        bool m_characterAnimationPlaybackMotionInstanceAvailableAfter = false;
        AZStd::string m_characterAnimationPlaybackEntityStateBeforeObservation;
        bool m_characterAnimationPlaybackEntityActiveBeforeObservation = false;
        bool m_characterAnimationPlaybackEntityValidBeforeObservation = false;
        bool m_characterAnimationPlaybackProbeComplete = false;
        bool m_characterAnimationPlaybackError = false;
        AZ::u64 m_characterAnimationPlaybackReadinessStartTick = 0;
        AZ::u64 m_characterAnimationPlaybackStartTick = 0;
        AZ::u64 m_characterAnimationPlaybackObservationTicks = 8;
        float m_characterAnimationPlaybackTimeBefore = 0.0f;
        float m_characterAnimationPlaybackTimeAfter = 0.0f;
        float m_characterAnimationPlaybackDuration = 0.0f;
        AZ::EntityId m_characterAnimationPlaybackEntityRawId;
        AZStd::string m_characterAnimationPlaybackExpectedMotionAssetId;
        AZStd::string m_characterAnimationPlaybackEntityId;
        AZStd::string m_characterAnimationPlaybackMotionAssetId;
        AZStd::string m_characterAnimationPlaybackBlocker;
        AZStd::mutex m_characterSpawnMutex;
    };
} // namespace MaxineRuntimeExitFixture
