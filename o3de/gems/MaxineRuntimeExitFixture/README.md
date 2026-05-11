# MAXINE Runtime Exit Fixture

This repo-owned O3DE Code Gem is a non-shipping runtime harness fixture. It is disabled by default and is intended only for controlled, bounded runtime command-envelope diagnostics.

The fixture source validates the after-initialization pattern discovered in local O3DE source:

- `AZ::Component::Activate`
- `AZ::TickBus::OnTick`
- `AzFramework::ApplicationRequests::ExitMainLoop`

Runtime harness gates must remain separate from the Gem source:

- `MAXINE_ENABLE_O3DE_RUNTIME_HARNESS=1`
- `MAXINE_ALLOW_LIVE_RUNTIME_COMMANDS=1`
- `MAXINE_ENABLE_RUNTIME_EXIT_FIXTURE=1`

The component also requires Settings Registry keys before it connects to `AZ::TickBus`:

- `/Amazon/MAXINE/RuntimeHarness/EnableExitFixture=true`
- `/Amazon/MAXINE/RuntimeHarness/ExitAfterTicks=<positive integer>`

Source readiness is not runtime execution proof. Rebuild readiness is not runtime execution proof. A future clean fixture exit can prove only bounded runtime command-envelope execution, not runtime character proof.
