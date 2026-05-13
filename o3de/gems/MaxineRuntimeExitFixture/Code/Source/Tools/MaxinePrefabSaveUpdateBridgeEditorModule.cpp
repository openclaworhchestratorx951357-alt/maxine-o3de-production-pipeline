#include "PrefabSaveUpdateBridgeHostComponent.h"

#include <AzCore/Memory/SystemAllocator.h>
#include <AzCore/Module/Module.h>

namespace MaxineRuntimeExitFixture
{
    class MaxinePrefabSaveUpdateBridgeEditorModule
        : public AZ::Module
    {
    public:
        AZ_RTTI(MaxinePrefabSaveUpdateBridgeEditorModule, "{93DC06D1-3E5B-4B2D-8787-F6F93BDF5F5D}", AZ::Module);
        AZ_CLASS_ALLOCATOR(MaxinePrefabSaveUpdateBridgeEditorModule, AZ::SystemAllocator);

        MaxinePrefabSaveUpdateBridgeEditorModule()
            : AZ::Module()
        {
            m_descriptors.insert(
                m_descriptors.end(),
                {
                    PrefabSaveUpdateBridgeHostComponent::CreateDescriptor(),
                });
        }

        AZ::ComponentTypeList GetRequiredSystemComponents() const override
        {
            return AZ::ComponentTypeList{
                azrtti_typeid<PrefabSaveUpdateBridgeHostComponent>(),
            };
        }
    };
} // namespace MaxineRuntimeExitFixture

#if defined(O3DE_GEM_NAME)
AZ_DECLARE_MODULE_CLASS(AZ_JOIN(Gem_, O3DE_GEM_NAME, _Editor), MaxineRuntimeExitFixture::MaxinePrefabSaveUpdateBridgeEditorModule)
#else
AZ_DECLARE_MODULE_CLASS(Gem_MaxineRuntimeExitFixture_Editor, MaxineRuntimeExitFixture::MaxinePrefabSaveUpdateBridgeEditorModule)
#endif
