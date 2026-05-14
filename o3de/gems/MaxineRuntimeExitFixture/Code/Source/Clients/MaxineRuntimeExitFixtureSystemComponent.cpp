#include "MaxineRuntimeExitFixtureSystemComponent.h"

#include <AzCore/Asset/AssetManager.h>
#include <AzCore/Asset/AssetManagerBus.h>
#include <AzCore/Component/Component.h>
#include <AzCore/Component/Entity.h>
#include <AzCore/Interface/Interface.h>
#include <AzCore/Serialization/SerializeContext.h>
#include <AzCore/Settings/SettingsRegistry.h>
#include <AzCore/std/parallel/lock.h>
#include <AzCore/std/string/fixed_string.h>
#include <AzFramework/Entity/GameEntityContextBus.h>
#include <AzFramework/API/ApplicationAPI.h>
#include <AzFramework/Spawnable/Spawnable.h>
#include <AzFramework/Spawnable/SpawnableEntitiesInterface.h>
#include <Integration/Components/ActorComponent.h>
#include <Integration/Components/SimpleMotionComponent.h>

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
        constexpr const char* EnableCharacterSpawnInstantiationProbeKey =
            "/Amazon/MAXINE/RuntimeHarness/EnableCharacterSpawnInstantiationProbe";
        constexpr const char* CharacterSpawnInstantiationProbeSpawnableProductPathKey =
            "/Amazon/MAXINE/RuntimeHarness/CharacterSpawnInstantiationProbe/SpawnableProductPath";
        constexpr const char* CharacterSpawnInstantiationProbeSpawnableCatalogPathKey =
            "/Amazon/MAXINE/RuntimeHarness/CharacterSpawnInstantiationProbe/SpawnableCatalogPath";
        constexpr const char* CharacterSpawnInstantiationProbeSpawnableAssetIdKey =
            "/Amazon/MAXINE/RuntimeHarness/CharacterSpawnInstantiationProbe/SpawnableAssetId";
        constexpr const char* CharacterSpawnInstantiationProbeSpawnableAssetTypeKey =
            "/Amazon/MAXINE/RuntimeHarness/CharacterSpawnInstantiationProbe/SpawnableAssetType";
        constexpr const char* CharacterSpawnInstantiationProbeTimeoutTicksKey =
            "/Amazon/MAXINE/RuntimeHarness/CharacterSpawnInstantiationProbe/TimeoutTicks";
        constexpr const char* CharacterSpawnInstantiationProbeRequirePositiveEntityCountKey =
            "/Amazon/MAXINE/RuntimeHarness/CharacterSpawnInstantiationProbe/RequirePositiveEntityCount";
        constexpr const char* CharacterSpawnInstantiationProbeCleanupSpawnedEntitiesKey =
            "/Amazon/MAXINE/RuntimeHarness/CharacterSpawnInstantiationProbe/CleanupSpawnedEntities";
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

        AZStd::string SanitizeMarkerValue(AZStd::string value)
        {
            for (char& character : value)
            {
                if (character == ' ' || character == '\t' || character == '\r' || character == '\n')
                {
                    character = '_';
                }
            }
            return value;
        }

        AZStd::string ComponentInventoryString(const AZ::Entity& entity)
        {
            AZStd::string components;
            for (const AZ::Component* component : entity.GetComponents())
            {
                if (component == nullptr)
                {
                    continue;
                }
                if (!components.empty())
                {
                    components += ";";
                }
                components += component->GetUnderlyingComponentType().ToString<AZStd::string>();
            }
            return components;
        }

        AZStd::string RuntimeActorAssetIdString(const AZ::Entity& entity)
        {
            for (const AZ::Component* component : entity.GetComponents())
            {
                const auto* actorComponent = azrtti_cast<const EMotionFX::Integration::ActorComponent*>(component);
                if (actorComponent != nullptr)
                {
                    return AssetIdToString(actorComponent->GetActorAsset().GetId());
                }
            }
            return {};
        }

        AZStd::string RuntimeSimpleMotionAssetIdString(const AZ::Entity& entity)
        {
            for (const AZ::Component* component : entity.GetComponents())
            {
                const auto* simpleMotionComponent = azrtti_cast<const EMotionFX::Integration::SimpleMotionComponent*>(component);
                if (simpleMotionComponent != nullptr)
                {
                    return AssetIdToString(simpleMotionComponent->GetMotion());
                }
            }
            return {};
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
        ConfigureCharacterSpawnInstantiationProbe();
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
        ReleaseCharacterSpawnInstantiationProbe();
        m_characterSpawnProbeEnabled = false;
        m_characterSpawnProbeStarted = false;
        m_characterSpawnProbeComplete = false;
        m_characterSpawnLoadRequested = false;
        m_characterSpawnReady = false;
        m_characterSpawnRequestIssued = false;
        m_characterSpawnCompletionObserved = false;
        m_characterSpawnCleanupRequested = false;
        m_characterSpawnCleanupComplete = false;
        m_characterSpawnRequirePositiveEntityCount = true;
        m_characterSpawnCleanupSpawnedEntities = true;
        m_characterSpawnError = false;
        m_characterSpawnTimeout = false;
        m_characterSpawnTimeoutTicks = 0;
        m_characterSpawnStartTick = 0;
        m_characterSpawnProductPath.clear();
        m_characterSpawnCatalogPath.clear();
        m_characterSpawnExpectedAssetId.clear();
        m_characterSpawnExpectedAssetType.clear();
        m_characterSpawnAssetId.SetInvalid();
        m_characterSpawnAssetType = AZ::Data::AssetType::CreateNull();
        m_characterSpawnedEntityIds.clear();
        m_characterSpawnedEntityNames.clear();
        m_characterSpawnedEntityComponentInventory.clear();
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

        if (m_characterSpawnProbeEnabled)
        {
            if (!m_characterSpawnProbeStarted)
            {
                StartCharacterSpawnInstantiationProbe();
            }
            PollCharacterSpawnInstantiationProbe();
            if (!m_characterSpawnProbeComplete)
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

    void MaxineRuntimeExitFixtureSystemComponent::ConfigureCharacterSpawnInstantiationProbe()
    {
        m_characterSpawnProbeEnabled = false;
        m_characterSpawnProbeStarted = false;
        m_characterSpawnProbeComplete = false;
        m_characterSpawnLoadRequested = false;
        m_characterSpawnReady = false;
        m_characterSpawnRequestIssued = false;
        m_characterSpawnCompletionObserved = false;
        m_characterSpawnCleanupRequested = false;
        m_characterSpawnCleanupComplete = false;
        m_characterSpawnError = false;
        m_characterSpawnTimeout = false;
        m_characterSpawnStartTick = 0;
        m_characterSpawnAssetId.SetInvalid();
        m_characterSpawnAssetType = AZ::Data::AssetType::CreateNull();
        m_characterSpawnedEntityIds.clear();
        m_characterSpawnedEntityNames.clear();
        m_characterSpawnedEntityComponentInventory.clear();

        auto* settingsRegistry = AZ::SettingsRegistry::Get();
        if (settingsRegistry == nullptr)
        {
            return;
        }

        bool enableProbe = false;
        AZ::s64 timeoutTicks = 0;
        settingsRegistry->Get(enableProbe, EnableCharacterSpawnInstantiationProbeKey);
        settingsRegistry->Get(timeoutTicks, CharacterSpawnInstantiationProbeTimeoutTicksKey);
        settingsRegistry->Get(
            m_characterSpawnRequirePositiveEntityCount,
            CharacterSpawnInstantiationProbeRequirePositiveEntityCountKey);
        settingsRegistry->Get(
            m_characterSpawnCleanupSpawnedEntities,
            CharacterSpawnInstantiationProbeCleanupSpawnedEntitiesKey);

        if (!enableProbe)
        {
            return;
        }

        const auto ReadSpawnProbeValue = [settingsRegistry](const char* key) -> AZStd::string
        {
            AZ::SettingsRegistryInterface::FixedValueString value;
            if (settingsRegistry->Get(value, key))
            {
                return value.c_str();
            }
            return {};
        };

        m_characterSpawnProductPath = ReadSpawnProbeValue(CharacterSpawnInstantiationProbeSpawnableProductPathKey);
        m_characterSpawnCatalogPath = ReadSpawnProbeValue(CharacterSpawnInstantiationProbeSpawnableCatalogPathKey);
        m_characterSpawnExpectedAssetId = ReadSpawnProbeValue(CharacterSpawnInstantiationProbeSpawnableAssetIdKey);
        m_characterSpawnExpectedAssetType = ReadSpawnProbeValue(CharacterSpawnInstantiationProbeSpawnableAssetTypeKey);
        m_characterSpawnTimeoutTicks = timeoutTicks > 0 ? static_cast<AZ::u64>(timeoutTicks) : 120;
        m_characterSpawnProbeEnabled = true;
    }

    void MaxineRuntimeExitFixtureSystemComponent::StartCharacterSpawnInstantiationProbe()
    {
        m_characterSpawnProbeStarted = true;
        m_characterSpawnStartTick = m_ticksObserved;

        AZ_TracePrintf(
            TraceWindow,
            "MAXINE_RUNTIME_CHARACTER_SPAWN_START product_path=%s catalog_path=%s asset_id=%s asset_type=%s timeout_ticks=%llu require_positive_entity_count=%s cleanup=%s\n",
            m_characterSpawnProductPath.c_str(),
            m_characterSpawnCatalogPath.c_str(),
            m_characterSpawnExpectedAssetId.c_str(),
            m_characterSpawnExpectedAssetType.c_str(),
            static_cast<unsigned long long>(m_characterSpawnTimeoutTicks),
            m_characterSpawnRequirePositiveEntityCount ? "true" : "false",
            m_characterSpawnCleanupSpawnedEntities ? "true" : "false");

        AZ_TracePrintf(
            TraceWindow,
            "MAXINE_RUNTIME_CHARACTER_SPAWN_SOURCE_VALIDATED api=AzFramework::SpawnableEntitiesInterface::SpawnAllEntities status=pass\n");

        if (!AZ::Data::AssetManager::IsReady())
        {
            m_characterSpawnError = true;
            AZ_TracePrintf(TraceWindow, "MAXINE_RUNTIME_CHARACTER_SPAWN_ERROR error=asset_manager_not_ready\n");
            CompleteCharacterSpawnInstantiationProbe("fail");
            return;
        }

        if (AzFramework::SpawnableEntitiesInterface::Get() == nullptr)
        {
            m_characterSpawnError = true;
            AZ_TracePrintf(TraceWindow, "MAXINE_RUNTIME_CHARACTER_SPAWN_ERROR error=spawnable_entities_interface_missing\n");
            CompleteCharacterSpawnInstantiationProbe("fail");
            return;
        }

        AzFramework::EntityContextId contextId;
        AzFramework::GameEntityContextRequestBus::BroadcastResult(
            contextId,
            &AzFramework::GameEntityContextRequests::GetGameEntityContextId);
        if (contextId.IsNull())
        {
            m_characterSpawnError = true;
            AZ_TracePrintf(TraceWindow, "MAXINE_RUNTIME_CHARACTER_SPAWN_ERROR error=game_entity_context_missing\n");
            CompleteCharacterSpawnInstantiationProbe("fail");
            return;
        }

        AZ_TracePrintf(
            TraceWindow,
            "MAXINE_RUNTIME_CHARACTER_SPAWN_CONTEXT status=game_entity_context_available context_id=%s\n",
            contextId.ToString<AZStd::string>().c_str());

        AZ::Data::AssetCatalogRequestBus::BroadcastResult(
            m_characterSpawnAssetId,
            &AZ::Data::AssetCatalogRequests::GetAssetIdByPath,
            m_characterSpawnCatalogPath.c_str(),
            AZ::Data::s_invalidAssetType,
            false);
        if (!m_characterSpawnAssetId.IsValid() && !m_characterSpawnExpectedAssetId.empty())
        {
            m_characterSpawnAssetId = AZ::Data::AssetId::CreateString(m_characterSpawnExpectedAssetId);
        }
        if (!m_characterSpawnAssetId.IsValid())
        {
            m_characterSpawnError = true;
            AZ_TracePrintf(TraceWindow, "MAXINE_RUNTIME_CHARACTER_SPAWN_ERROR error=spawnable_asset_id_resolution_failed\n");
            CompleteCharacterSpawnInstantiationProbe("fail");
            return;
        }

        AZ::Data::AssetInfo assetInfo;
        AZ::Data::AssetCatalogRequestBus::BroadcastResult(
            assetInfo,
            &AZ::Data::AssetCatalogRequests::GetAssetInfoById,
            m_characterSpawnAssetId);
        m_characterSpawnAssetType = assetInfo.m_assetType;
        if (m_characterSpawnAssetType.IsNull())
        {
            m_characterSpawnError = true;
            AZ_TracePrintf(
                TraceWindow,
                "MAXINE_RUNTIME_CHARACTER_SPAWN_ERROR asset_id=%s error=spawnable_asset_type_resolution_failed\n",
                AssetIdToString(m_characterSpawnAssetId).c_str());
            CompleteCharacterSpawnInstantiationProbe("fail");
            return;
        }

        if (AZ::Data::AssetManager::Instance().GetHandler(m_characterSpawnAssetType) == nullptr)
        {
            m_characterSpawnError = true;
            AZ_TracePrintf(
                TraceWindow,
                "MAXINE_RUNTIME_CHARACTER_SPAWN_ERROR asset_id=%s asset_type=%s error=spawnable_asset_handler_missing\n",
                AssetIdToString(m_characterSpawnAssetId).c_str(),
                AssetTypeToString(m_characterSpawnAssetType).c_str());
            CompleteCharacterSpawnInstantiationProbe("fail");
            return;
        }

        m_characterSpawnAsset = AZ::Data::AssetManager::Instance().GetAsset<AzFramework::Spawnable>(
            m_characterSpawnAssetId,
            AZ::Data::AssetLoadBehavior::Default);
        m_characterSpawnLoadRequested = static_cast<bool>(m_characterSpawnAsset);
        if (!m_characterSpawnLoadRequested)
        {
            m_characterSpawnError = true;
            AZ_TracePrintf(
                TraceWindow,
                "MAXINE_RUNTIME_CHARACTER_SPAWN_ERROR asset_id=%s asset_type=%s error=spawnable_load_request_failed\n",
                AssetIdToString(m_characterSpawnAssetId).c_str(),
                AssetTypeToString(m_characterSpawnAssetType).c_str());
            CompleteCharacterSpawnInstantiationProbe("fail");
        }
    }

    void MaxineRuntimeExitFixtureSystemComponent::PollCharacterSpawnInstantiationProbe()
    {
        if (m_characterSpawnProbeComplete)
        {
            return;
        }

        const bool timedOut = (m_ticksObserved - m_characterSpawnStartTick) >= m_characterSpawnTimeoutTicks;
        if (timedOut && !m_characterSpawnTimeout)
        {
            m_characterSpawnTimeout = true;
            AZ_TracePrintf(
                TraceWindow,
                "MAXINE_RUNTIME_CHARACTER_SPAWN_TIMEOUT ticket=%u timeout_ticks=%llu\n",
                m_characterSpawnTicket.GetId(),
                static_cast<unsigned long long>(m_characterSpawnTimeoutTicks));
            CompleteCharacterSpawnInstantiationProbe("fail");
            return;
        }

        if (!m_characterSpawnReady)
        {
            if (m_characterSpawnAsset.IsReady())
            {
                m_characterSpawnReady = true;
            }
            else if (m_characterSpawnAsset.IsError())
            {
                m_characterSpawnError = true;
                AZ_TracePrintf(TraceWindow, "MAXINE_RUNTIME_CHARACTER_SPAWN_ERROR error=spawnable_asset_load_error\n");
                CompleteCharacterSpawnInstantiationProbe("fail");
                return;
            }
            else
            {
                return;
            }
        }

        auto* spawnableInterface = AzFramework::SpawnableEntitiesInterface::Get();
        if (spawnableInterface == nullptr)
        {
            m_characterSpawnError = true;
            AZ_TracePrintf(TraceWindow, "MAXINE_RUNTIME_CHARACTER_SPAWN_ERROR error=spawnable_entities_interface_missing\n");
            CompleteCharacterSpawnInstantiationProbe("fail");
            return;
        }

        if (!m_characterSpawnRequestIssued)
        {
            m_characterSpawnTicket = AzFramework::EntitySpawnTicket(m_characterSpawnAsset);
            if (!m_characterSpawnTicket.IsValid())
            {
                m_characterSpawnError = true;
                AZ_TracePrintf(TraceWindow, "MAXINE_RUNTIME_CHARACTER_SPAWN_ERROR error=spawn_ticket_invalid\n");
                CompleteCharacterSpawnInstantiationProbe("fail");
                return;
            }

            AZ_TracePrintf(
                TraceWindow,
                "MAXINE_RUNTIME_CHARACTER_SPAWN_TICKET ticket=%u valid=true\n",
                m_characterSpawnTicket.GetId());

            AzFramework::SpawnAllEntitiesOptionalArgs spawnArgs;
            spawnArgs.m_completionCallback =
                [this](AzFramework::EntitySpawnTicket::Id ticketId, AzFramework::SpawnableConstEntityContainerView view)
            {
                AZStd::lock_guard<AZStd::mutex> lock(m_characterSpawnMutex);
                m_characterSpawnCompletionObserved = true;
                m_characterSpawnedEntityIds.clear();
                m_characterSpawnedEntityNames.clear();
                m_characterSpawnedEntityComponentInventory.clear();

                AZ_TracePrintf(
                    TraceWindow,
                    "MAXINE_RUNTIME_CHARACTER_SPAWN_COMPLETED ticket=%u result=completed entity_count=%zu\n",
                    ticketId,
                    view.size());

                size_t index = 0;
                for (const AZ::Entity* entity : view)
                {
                    if (entity == nullptr)
                    {
                        continue;
                    }
                    const AZStd::string entityId = entity->GetId().ToString();
                    const AZStd::string entityName = SanitizeMarkerValue(entity->GetName());
                    const AZStd::string components = ComponentInventoryString(*entity);
                    const AZStd::string actorAssetId = RuntimeActorAssetIdString(*entity);
                    const AZStd::string motionAssetId = RuntimeSimpleMotionAssetIdString(*entity);
                    m_characterSpawnedEntityIds.push_back(entityId);
                    m_characterSpawnedEntityNames.push_back(entityName);
                    m_characterSpawnedEntityComponentInventory.push_back(components);

                    AZ_TracePrintf(
                        TraceWindow,
                        "MAXINE_RUNTIME_CHARACTER_SPAWN_ENTITY ticket=%u index=%zu entity_id=%s name=%s component_count=%zu components=%s actor_asset_id=%s motion_asset_id=%s\n",
                        ticketId,
                        index,
                        entityId.c_str(),
                        entityName.c_str(),
                        entity->GetComponents().size(),
                        components.c_str(),
                        actorAssetId.c_str(),
                        motionAssetId.c_str());
                    ++index;
                }
            };
            spawnableInterface->SpawnAllEntities(m_characterSpawnTicket, AZStd::move(spawnArgs));
            m_characterSpawnRequestIssued = true;
            AZ_TracePrintf(
                TraceWindow,
                "MAXINE_RUNTIME_CHARACTER_SPAWN_REQUESTED ticket=%u api=AzFramework::SpawnableEntitiesInterface::SpawnAllEntities\n",
                m_characterSpawnTicket.GetId());
            return;
        }

        if (!m_characterSpawnCompletionObserved)
        {
            return;
        }

        const bool positiveEntityCount = !m_characterSpawnedEntityIds.empty();
        if (m_characterSpawnRequirePositiveEntityCount && !positiveEntityCount)
        {
            m_characterSpawnError = true;
            AZ_TracePrintf(
                TraceWindow,
                "MAXINE_RUNTIME_CHARACTER_SPAWN_ERROR ticket=%u error=no_spawned_entities\n",
                m_characterSpawnTicket.GetId());
            CompleteCharacterSpawnInstantiationProbe("fail");
            return;
        }

        if (m_characterSpawnCleanupSpawnedEntities && !m_characterSpawnCleanupRequested)
        {
            AzFramework::DespawnAllEntitiesOptionalArgs despawnArgs;
            despawnArgs.m_completionCallback = [this](AzFramework::EntitySpawnTicket::Id ticketId)
            {
                AZStd::lock_guard<AZStd::mutex> lock(m_characterSpawnMutex);
                m_characterSpawnCleanupComplete = true;
                AZ_TracePrintf(
                    TraceWindow,
                    "MAXINE_RUNTIME_CHARACTER_SPAWN_CLEANUP ticket=%u status=complete\n",
                    ticketId);
            };
            spawnableInterface->DespawnAllEntities(m_characterSpawnTicket, AZStd::move(despawnArgs));
            m_characterSpawnCleanupRequested = true;
            return;
        }

        if (!m_characterSpawnCleanupSpawnedEntities)
        {
            m_characterSpawnCleanupComplete = true;
            AZ_TracePrintf(
                TraceWindow,
                "MAXINE_RUNTIME_CHARACTER_SPAWN_CLEANUP ticket=%u status=not_required\n",
                m_characterSpawnTicket.GetId());
        }

        if (m_characterSpawnCleanupComplete)
        {
            CompleteCharacterSpawnInstantiationProbe(m_characterSpawnError ? "fail" : "pass");
        }
    }

    void MaxineRuntimeExitFixtureSystemComponent::CompleteCharacterSpawnInstantiationProbe(const char* status)
    {
        if (m_characterSpawnProbeComplete)
        {
            return;
        }

        AZStd::lock_guard<AZStd::mutex> lock(m_characterSpawnMutex);
        const char* cleanupStatus =
            m_characterSpawnCleanupComplete
            ? (m_characterSpawnCleanupSpawnedEntities ? "complete" : "not_required")
            : (m_characterSpawnCleanupSpawnedEntities ? "incomplete" : "not_required");

        AZ_TracePrintf(
            TraceWindow,
            "MAXINE_RUNTIME_CHARACTER_SPAWN_SUMMARY status=%s requested=%u completed=%u spawned=%zu cleanup=%s timed_out=%u\n",
            status,
            m_characterSpawnRequestIssued ? 1 : 0,
            m_characterSpawnCompletionObserved ? 1 : 0,
            m_characterSpawnedEntityIds.size(),
            cleanupStatus,
            m_characterSpawnTimeout ? 1 : 0);
        m_characterSpawnProbeComplete = true;
    }

    void MaxineRuntimeExitFixtureSystemComponent::ReleaseCharacterSpawnInstantiationProbe()
    {
        m_characterSpawnAsset.Reset();
        m_characterSpawnTicket = AzFramework::EntitySpawnTicket();
    }
} // namespace MaxineRuntimeExitFixture
