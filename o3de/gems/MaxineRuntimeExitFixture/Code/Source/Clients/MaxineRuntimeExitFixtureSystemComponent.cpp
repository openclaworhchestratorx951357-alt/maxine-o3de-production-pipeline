#include "MaxineRuntimeExitFixtureSystemComponent.h"

#include <AzCore/Interface/Interface.h>
#include <AzCore/Serialization/SerializeContext.h>
#include <AzCore/Settings/SettingsRegistry.h>
#include <AzFramework/API/ApplicationAPI.h>

namespace MaxineRuntimeExitFixture
{
    namespace
    {
        constexpr const char* EnableExitFixtureKey = "/Amazon/MAXINE/RuntimeHarness/EnableExitFixture";
        constexpr const char* ExitAfterTicksKey = "/Amazon/MAXINE/RuntimeHarness/ExitAfterTicks";
        constexpr const char* TraceWindow = "MaxineRuntimeExitFixture";
    } // namespace

    AZ_COMPONENT_IMPL(
        MaxineRuntimeExitFixtureSystemComponent,
        "MaxineRuntimeExitFixtureSystemComponent",
        "{0EE6CDAE-3F50-4C02-9E65-1F17D64316B1}");

    void MaxineRuntimeExitFixtureSystemComponent::Reflect(AZ::ReflectContext* context)
    {
        if (auto serializeContext = azrtti_cast<AZ::SerializeContext*>(context))
        {
            serializeContext->Class<MaxineRuntimeExitFixtureSystemComponent, AZ::Component>()->Version(1);
        }
    }

    void MaxineRuntimeExitFixtureSystemComponent::GetProvidedServices(AZ::ComponentDescriptor::DependencyArrayType& provided)
    {
        provided.push_back(AZ_CRC_CE("MaxineRuntimeExitFixtureService"));
    }

    void MaxineRuntimeExitFixtureSystemComponent::GetIncompatibleServices(AZ::ComponentDescriptor::DependencyArrayType& incompatible)
    {
        incompatible.push_back(AZ_CRC_CE("MaxineRuntimeExitFixtureService"));
    }

    void MaxineRuntimeExitFixtureSystemComponent::GetRequiredServices(AZ::ComponentDescriptor::DependencyArrayType& required)
    {
        AZ_UNUSED(required);
    }

    void MaxineRuntimeExitFixtureSystemComponent::GetDependentServices(AZ::ComponentDescriptor::DependencyArrayType& dependent)
    {
        AZ_UNUSED(dependent);
    }

    void MaxineRuntimeExitFixtureSystemComponent::Activate()
    {
        bool enableFixture = false;
        AZ::s64 exitAfterTicks = 0;

        if (auto* settingsRegistry = AZ::SettingsRegistry::Get(); settingsRegistry != nullptr)
        {
            settingsRegistry->Get(enableFixture, EnableExitFixtureKey);
            settingsRegistry->Get(exitAfterTicks, ExitAfterTicksKey);
        }

        if (!enableFixture || exitAfterTicks <= 0)
        {
            AZ_TracePrintf(
                TraceWindow,
                "MAXINE_RUNTIME_EXIT_FIXTURE_DISABLED enable=%s exit_after_ticks=%lld\n",
                enableFixture ? "true" : "false",
                static_cast<long long>(exitAfterTicks));
            return;
        }

        m_enabled = true;
        m_exitAfterTicks = static_cast<AZ::u64>(exitAfterTicks);
        m_ticksObserved = 0;
        AZ::TickBus::Handler::BusConnect();

        AZ_TracePrintf(
            TraceWindow,
            "MAXINE_RUNTIME_EXIT_FIXTURE_ARMED exit_after_ticks=%llu\n",
            static_cast<unsigned long long>(m_exitAfterTicks));
    }

    void MaxineRuntimeExitFixtureSystemComponent::Deactivate()
    {
        if (AZ::TickBus::Handler::BusIsConnected())
        {
            AZ::TickBus::Handler::BusDisconnect();
        }
        m_enabled = false;
        m_exitAfterTicks = 0;
        m_ticksObserved = 0;
    }

    void MaxineRuntimeExitFixtureSystemComponent::OnTick([[maybe_unused]] float deltaTime, [[maybe_unused]] AZ::ScriptTimePoint time)
    {
        if (!m_enabled)
        {
            return;
        }

        ++m_ticksObserved;
        if (m_ticksObserved < m_exitAfterTicks)
        {
            return;
        }

        m_enabled = false;
        if (AZ::TickBus::Handler::BusIsConnected())
        {
            AZ::TickBus::Handler::BusDisconnect();
        }

        AZ_TracePrintf(
            TraceWindow,
            "MAXINE_RUNTIME_EXIT_FIXTURE_REQUESTING_EXIT ticks_observed=%llu\n",
            static_cast<unsigned long long>(m_ticksObserved));
        AzFramework::ApplicationRequests::Bus::Broadcast(&AzFramework::ApplicationRequests::ExitMainLoop);
    }
} // namespace MaxineRuntimeExitFixture
