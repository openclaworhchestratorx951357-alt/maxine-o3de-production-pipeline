#include "MaxineRuntimeExitFixtureSystemComponent.h"

#include <AzCore/Asset/AssetManager.h>
#include <AzCore/Asset/AssetManagerBus.h>
#include <AzCore/Interface/Interface.h>
#include <AzCore/Serialization/SerializeContext.h>
#include <AzCore/Settings/SettingsRegistry.h>
#include <AzCore/std/string/fixed_string.h>
#include <AzFramework/API/ApplicationAPI.h>

namespace MaxineRuntimeExitFixture
{
    namespace
    {
        constexpr const char* EnableExitFixtureKey = "/Amazon/MAXINE/RuntimeHarness/EnableExitFixture";
        constexpr const char* ExitAfterTicksKey = "/Amazon/MAXINE/RuntimeHarness/ExitAfterTicks";
        constexpr const char* EnableCharacterProductLoadProbeKey = "/Amazon/MAXINE/RuntimeHarness/EnableCharacterProductLoadProbe";
        constexpr const char* CharacterProductLoadProbeProductCountKey =
            "/Amazon/MAXINE/RuntimeHarness/CharacterProductLoadProbe/ProductCount";
        constexpr const char* CharacterProductLoadProbeProductSpecsKey =
            "/Amazon/MAXINE/RuntimeHarness/CharacterProductLoadProbe/ProductSpecs";
        constexpr const char* CharacterProductLoadProbeProductSpecsHexKey =
            "/Amazon/MAXINE/RuntimeHarness/CharacterProductLoadProbe/ProductSpecsHex";
        constexpr const char* CharacterProductLoadProbeTimeoutTicksKey =
            "/Amazon/MAXINE/RuntimeHarness/CharacterProductLoadProbe/TimeoutTicks";
        constexpr const char* CharacterProductLoadProbeRequireAllProductsReadyKey =
            "/Amazon/MAXINE/RuntimeHarness/CharacterProductLoadProbe/RequireAllProductsReady";
        constexpr const char* TraceWindow = "MaxineRuntimeExitFixture";

        AZStd::string ProductProbeKey(AZ::u64 index, const char* field)
        {
            return AZStd::string::format(
                "/Amazon/MAXINE/RuntimeHarness/CharacterProductLoadProbe/Products/%llu/%s",
                static_cast<unsigned long long>(index),
                field);
        }

        AZStd::string AssetIdToString(const AZ::Data::AssetId& assetId)
        {
            return assetId.ToString<AZStd::string>();
        }

        AZStd::string AssetTypeToString(const AZ::Data::AssetType& assetType)
        {
            return assetType.ToString<AZStd::string>();
        }

        AZStd::vector<AZStd::string> SplitProductLoadSpec(const AZStd::string& value, char delimiter)
        {
            AZStd::vector<AZStd::string> parts;
            size_t start = 0;
            while (start <= value.size())
            {
                const size_t end = value.find(delimiter, start);
                if (end == AZStd::string::npos)
                {
                    parts.push_back(value.substr(start));
                    break;
                }
                parts.push_back(value.substr(start, end - start));
                start = end + 1;
            }
            return parts;
        }

        int ProductLoadSpecHexNibble(char value)
        {
            if (value >= '0' && value <= '9')
            {
                return value - '0';
            }
            if (value >= 'a' && value <= 'f')
            {
                return value - 'a' + 10;
            }
            if (value >= 'A' && value <= 'F')
            {
                return value - 'A' + 10;
            }
            return -1;
        }

        AZStd::string DecodeProductLoadSpecHex(const AZStd::string& value)
        {
            AZStd::string decoded;
            if ((value.size() % 2) != 0)
            {
                return decoded;
            }

            decoded.reserve(value.size() / 2);
            for (size_t index = 0; index < value.size(); index += 2)
            {
                const int high = ProductLoadSpecHexNibble(value[index]);
                const int low = ProductLoadSpecHexNibble(value[index + 1]);
                if (high < 0 || low < 0)
                {
                    decoded.clear();
                    return decoded;
                }
                decoded.push_back(static_cast<char>((high << 4) | low));
            }
            return decoded;
        }

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
        ConfigureProductLoadProbe();
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
        ReleaseProductLoadProbeAssets();
        m_productLoadProbeEnabled = false;
        m_productLoadProbeStarted = false;
        m_productLoadProbeComplete = false;
        m_requireAllProductsReady = true;
        m_productLoadTimeoutTicks = 0;
        m_productLoadStartTick = 0;
        m_productLoadProducts.clear();
    }

    void MaxineRuntimeExitFixtureSystemComponent::OnTick([[maybe_unused]] float deltaTime, [[maybe_unused]] AZ::ScriptTimePoint time)
    {
        if (!m_enabled)
        {
            return;
        }

        ++m_ticksObserved;
        if (m_productLoadProbeEnabled)
        {
            if (!m_productLoadProbeStarted)
            {
                StartProductLoadProbe();
            }
            PollProductLoadProbe();
            if (!m_productLoadProbeComplete)
            {
                return;
            }
        }

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

    void MaxineRuntimeExitFixtureSystemComponent::ConfigureProductLoadProbe()
    {
        m_productLoadProbeEnabled = false;
        m_productLoadProbeStarted = false;
        m_productLoadProbeComplete = false;
        m_productLoadProducts.clear();

        bool enableProbe = false;
        bool requireAllProductsReady = true;
        AZ::s64 productCount = 0;
        AZ::s64 timeoutTicks = 0;

        auto* settingsRegistry = AZ::SettingsRegistry::Get();
        if (settingsRegistry == nullptr)
        {
            return;
        }

        settingsRegistry->Get(enableProbe, EnableCharacterProductLoadProbeKey);
        settingsRegistry->Get(productCount, CharacterProductLoadProbeProductCountKey);
        settingsRegistry->Get(timeoutTicks, CharacterProductLoadProbeTimeoutTicksKey);
        settingsRegistry->Get(requireAllProductsReady, CharacterProductLoadProbeRequireAllProductsReadyKey);

        if (!enableProbe)
        {
            return;
        }

        m_productLoadProbeEnabled = true;
        m_requireAllProductsReady = requireAllProductsReady;
        m_productLoadTimeoutTicks = timeoutTicks > 0 ? static_cast<AZ::u64>(timeoutTicks) : 120;

        AZStd::string productSpecsValue;
        AZ::SettingsRegistryInterface::FixedValueString productSpecsHex;
        if (settingsRegistry->Get(productSpecsHex, CharacterProductLoadProbeProductSpecsHexKey))
        {
            productSpecsValue = DecodeProductLoadSpecHex(productSpecsHex.c_str());
        }
        if (productSpecsValue.empty())
        {
            AZ::SettingsRegistryInterface::FixedValueString productSpecs;
            if (settingsRegistry->Get(productSpecs, CharacterProductLoadProbeProductSpecsKey))
            {
                productSpecsValue = productSpecs.c_str();
            }
        }

        if (!productSpecsValue.empty())
        {
            for (const AZStd::string& spec : SplitProductLoadSpec(productSpecsValue, ','))
            {
                ProductLoadProbeEntry entry;
                const AZStd::vector<AZStd::string> fields = SplitProductLoadSpec(spec, '|');
                if (fields.size() >= 4)
                {
                    entry.m_kind = fields[0];
                    entry.m_productPath = fields[1];
                    entry.m_catalogPath = fields[2];
                    entry.m_expectedCategory = fields[3];
                }
                if (!entry.m_kind.empty() && !entry.m_catalogPath.empty())
                {
                    m_productLoadProducts.push_back(AZStd::move(entry));
                }
            }
        }

        if (!m_productLoadProducts.empty())
        {
            return;
        }

        for (AZ::s64 index = 0; index < productCount; ++index)
        {
            ProductLoadProbeEntry entry;
            const auto ReadProductProbeValue = [settingsRegistry, index](const char* suffix) -> AZStd::string
            {
                AZ::SettingsRegistryInterface::FixedValueString value;
                if (settingsRegistry->Get(value, ProductProbeKey(static_cast<AZ::u64>(index), suffix).c_str()))
                {
                    return value.c_str();
                }
                return {};
            };

            entry.m_kind = ReadProductProbeValue("Kind");
            entry.m_productPath = ReadProductProbeValue("ProductPath");
            entry.m_catalogPath = ReadProductProbeValue("CatalogPath");
            entry.m_expectedCategory = ReadProductProbeValue("ExpectedCategory");

            if (!entry.m_kind.empty() && !entry.m_catalogPath.empty())
            {
                m_productLoadProducts.push_back(AZStd::move(entry));
            }
        }
    }

    void MaxineRuntimeExitFixtureSystemComponent::StartProductLoadProbe()
    {
        m_productLoadProbeStarted = true;
        m_productLoadStartTick = m_ticksObserved;

        AZ_TracePrintf(
            TraceWindow,
            "MAXINE_RUNTIME_PRODUCT_LOAD_START count=%zu timeout_ticks=%llu require_all=%s\n",
            m_productLoadProducts.size(),
            static_cast<unsigned long long>(m_productLoadTimeoutTicks),
            m_requireAllProductsReady ? "true" : "false");

        if (m_productLoadProducts.empty() || !AZ::Data::AssetManager::IsReady())
        {
            AZ_TracePrintf(
                TraceWindow,
                "MAXINE_RUNTIME_PRODUCT_LOAD_SUMMARY status=fail required=%zu ready=0 failed=%zu timed_out=0\n",
                m_productLoadProducts.size(),
                m_productLoadProducts.empty() ? 1 : m_productLoadProducts.size());
            m_productLoadProbeComplete = true;
            return;
        }

        for (size_t index = 0; index < m_productLoadProducts.size(); ++index)
        {
            ProductLoadProbeEntry& product = m_productLoadProducts[index];
            AZ::Data::AssetCatalogRequestBus::BroadcastResult(
                product.m_assetId,
                &AZ::Data::AssetCatalogRequests::GetAssetIdByPath,
                product.m_catalogPath.c_str(),
                AZ::Data::s_invalidAssetType,
                false);

            if (!product.m_assetId.IsValid())
            {
                product.m_error = true;
                AZ_TracePrintf(
                    TraceWindow,
                    "MAXINE_RUNTIME_PRODUCT_LOAD_ERROR index=%zu kind=%s path=%s catalog_path=%s error=asset_id_resolution_failed\n",
                    index,
                    product.m_kind.c_str(),
                    product.m_productPath.c_str(),
                    product.m_catalogPath.c_str());
                continue;
            }

            AZ::Data::AssetInfo assetInfo;
            AZ::Data::AssetCatalogRequestBus::BroadcastResult(
                assetInfo,
                &AZ::Data::AssetCatalogRequests::GetAssetInfoById,
                product.m_assetId);
            product.m_assetType = assetInfo.m_assetType;

            if (product.m_assetType.IsNull())
            {
                product.m_error = true;
                AZ_TracePrintf(
                    TraceWindow,
                    "MAXINE_RUNTIME_PRODUCT_LOAD_ERROR index=%zu kind=%s path=%s catalog_path=%s asset_id=%s error=asset_type_resolution_failed\n",
                    index,
                    product.m_kind.c_str(),
                    product.m_productPath.c_str(),
                    product.m_catalogPath.c_str(),
                    AssetIdToString(product.m_assetId).c_str());
                continue;
            }

            if (AZ::Data::AssetManager::Instance().GetHandler(product.m_assetType) == nullptr)
            {
                product.m_error = true;
                AZ_TracePrintf(
                    TraceWindow,
                    "MAXINE_RUNTIME_PRODUCT_LOAD_ERROR index=%zu kind=%s path=%s catalog_path=%s asset_id=%s asset_type=%s error=asset_handler_missing\n",
                    index,
                    product.m_kind.c_str(),
                    product.m_productPath.c_str(),
                    product.m_catalogPath.c_str(),
                    AssetIdToString(product.m_assetId).c_str(),
                    AssetTypeToString(product.m_assetType).c_str());
                continue;
            }

            product.m_resolved = true;
            product.m_asset = AZ::Data::AssetManager::Instance().GetAsset(
                product.m_assetId,
                product.m_assetType,
                AZ::Data::AssetLoadBehavior::Default);
            product.m_loadRequested = static_cast<bool>(product.m_asset);

            AZ_TracePrintf(
                TraceWindow,
                "MAXINE_RUNTIME_PRODUCT_LOAD_RESOLVED index=%zu kind=%s path=%s catalog_path=%s asset_id=%s asset_type=%s asset_type_name=runtime_catalog_asset_type\n",
                index,
                product.m_kind.c_str(),
                product.m_productPath.c_str(),
                product.m_catalogPath.c_str(),
                AssetIdToString(product.m_assetId).c_str(),
                AssetTypeToString(product.m_assetType).c_str());
        }
    }

    void MaxineRuntimeExitFixtureSystemComponent::PollProductLoadProbe()
    {
        if (m_productLoadProbeComplete)
        {
            return;
        }

        size_t readyCount = 0;
        size_t failedCount = 0;
        size_t timeoutCount = 0;
        const bool timedOut = (m_ticksObserved - m_productLoadStartTick) >= m_productLoadTimeoutTicks;

        for (size_t index = 0; index < m_productLoadProducts.size(); ++index)
        {
            ProductLoadProbeEntry& product = m_productLoadProducts[index];
            if (product.m_ready)
            {
                ++readyCount;
                continue;
            }
            if (product.m_error)
            {
                ++failedCount;
                continue;
            }
            if (product.m_timeout)
            {
                ++timeoutCount;
                continue;
            }

            if (product.m_asset.IsReady())
            {
                product.m_ready = true;
                ++readyCount;
                AZ_TracePrintf(
                    TraceWindow,
                    "MAXINE_RUNTIME_PRODUCT_LOAD_READY index=%zu kind=%s path=%s status=ready\n",
                    index,
                    product.m_kind.c_str(),
                    product.m_productPath.c_str());
            }
            else if (product.m_asset.IsError())
            {
                product.m_error = true;
                ++failedCount;
                AZ_TracePrintf(
                    TraceWindow,
                    "MAXINE_RUNTIME_PRODUCT_LOAD_ERROR index=%zu kind=%s path=%s error=asset_load_error\n",
                    index,
                    product.m_kind.c_str(),
                    product.m_productPath.c_str());
            }
            else if (timedOut)
            {
                product.m_timeout = true;
                ++timeoutCount;
                AZ_TracePrintf(
                    TraceWindow,
                    "MAXINE_RUNTIME_PRODUCT_LOAD_TIMEOUT index=%zu kind=%s path=%s timeout=true\n",
                    index,
                    product.m_kind.c_str(),
                    product.m_productPath.c_str());
            }
        }

        const bool allReady = readyCount == m_productLoadProducts.size() && !m_productLoadProducts.empty();
        const bool allFinished = readyCount + failedCount + timeoutCount == m_productLoadProducts.size();
        if (allReady || allFinished)
        {
            CompleteProductLoadProbe(allReady ? "pass" : "fail");
        }
    }

    void MaxineRuntimeExitFixtureSystemComponent::CompleteProductLoadProbe(const char* status)
    {
        size_t readyCount = 0;
        size_t failedCount = 0;
        size_t timeoutCount = 0;
        for (const ProductLoadProbeEntry& product : m_productLoadProducts)
        {
            readyCount += product.m_ready ? 1 : 0;
            failedCount += product.m_error ? 1 : 0;
            timeoutCount += product.m_timeout ? 1 : 0;
        }

        AZ_TracePrintf(
            TraceWindow,
            "MAXINE_RUNTIME_PRODUCT_LOAD_SUMMARY status=%s required=%zu ready=%zu failed=%zu timed_out=%zu\n",
            status,
            m_productLoadProducts.size(),
            readyCount,
            failedCount,
            timeoutCount);
        ReleaseProductLoadProbeAssets();
        m_productLoadProbeComplete = true;
    }

    void MaxineRuntimeExitFixtureSystemComponent::ReleaseProductLoadProbeAssets()
    {
        for (size_t index = 0; index < m_productLoadProducts.size(); ++index)
        {
            ProductLoadProbeEntry& product = m_productLoadProducts[index];
            if (product.m_released)
            {
                continue;
            }
            product.m_asset.Reset();
            product.m_released = true;
            AZ_TracePrintf(
                TraceWindow,
                "MAXINE_RUNTIME_PRODUCT_LOAD_RELEASED index=%zu kind=%s path=%s status=released\n",
                index,
                product.m_kind.c_str(),
                product.m_productPath.c_str());
        }
    }
} // namespace MaxineRuntimeExitFixture
