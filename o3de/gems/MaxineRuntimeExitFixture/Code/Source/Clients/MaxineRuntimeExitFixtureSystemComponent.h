#pragma once

#include <AzCore/Component/Component.h>
#include <AzCore/Component/TickBus.h>
#include <AzCore/Asset/AssetCommon.h>
#include <AzCore/std/string/string.h>
#include <AzCore/std/containers/vector.h>

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
    };
} // namespace MaxineRuntimeExitFixture
