#include "MaxineRuntimeExitFixtureSystemComponent.h"

#include <AzCore/Memory/SystemAllocator.h>
#include <AzCore/Module/Module.h>

namespace MaxineRuntimeExitFixture
{
    class MaxineRuntimeExitFixtureModule
        : public AZ::Module
    {
    public:
        AZ_RTTI(MaxineRuntimeExitFixtureModule, "{29C96E26-2210-4E4A-B2A0-2E8058D9EA21}", AZ::Module);
        AZ_CLASS_ALLOCATOR(MaxineRuntimeExitFixtureModule, AZ::SystemAllocator);

        MaxineRuntimeExitFixtureModule()
            : AZ::Module()
        {
            m_descriptors.insert(
                m_descriptors.end(),
                {
                    MaxineRuntimeExitFixtureSystemComponent::CreateDescriptor(),
                });
        }

        AZ::ComponentTypeList GetRequiredSystemComponents() const override
        {
            return AZ::ComponentTypeList{
                azrtti_typeid<MaxineRuntimeExitFixtureSystemComponent>(),
            };
        }
    };
} // namespace MaxineRuntimeExitFixture

#if defined(O3DE_GEM_NAME)
AZ_DECLARE_MODULE_CLASS(AZ_JOIN(Gem_, O3DE_GEM_NAME), MaxineRuntimeExitFixture::MaxineRuntimeExitFixtureModule)
#else
AZ_DECLARE_MODULE_CLASS(Gem_MaxineRuntimeExitFixture, MaxineRuntimeExitFixture::MaxineRuntimeExitFixtureModule)
#endif
