---
trigger: model_decision
description: When working on Fiori frontend code
---

SAP Fiori-Focused IDE Workflow Rule (Windsurf)
Implementation Principles
Behavior Rules – SAP Fiori Frontend Focus
You have one mission: implement exactly what is requested in the SAP Fiori UI layer.
Produce SAPUI5/Fiori frontend code (XML views, JS controllers, JSON models, annotations-based UIs, manifest/app configuration) that implements precisely what was requested — no additional features, no creative extensions.
Do not introduce extra UI elements (buttons, fields, filters, dialogs), additional routes, or extra services/odata calls unless explicitly requested.
Always prefer standard SAP Fiori UX patterns and SAPUI5 controls in their simplest form that satisfies the requirement (e.g., sap.m.Table vs. complex custom controls unless explicitly asked).
At each step, ask yourself:
“Am I adding any UI, binding, event handler, or configuration that wasn’t explicitly requested?”
Progressive Development
Implement Fiori UI changes in logical stages rather than all at once:
Stage examples: view layout (XML), model/binding wiring, controller logic (event handlers), i18n text wiring, navigation/routing updates.
After each meaningful frontend component is completed, pause and check it against the requirements:
Does the view show exactly the requested fields and controls?
Are bindings and formats only as specified?
Confirm scope understanding before:
Adding new views/fragments
Changing routing (manifest.json)
Introducing new models (OData/JSON/Resource)
Scope Management
Implement only what is explicitly requested in the Fiori/frontend scope.
When requirements are ambiguous, choose the minimal viable Fiori implementation:
Minimal number of controls
Minimal controller logic
Minimal config changes in manifest.json
Identify when a request might impact multiple Fiori artifacts:
XML view + controller
Component.js + manifest routing
i18n texts + formatter
Always ask permission before:
Modifying views or fragments not explicitly mentioned
Extending standard Fiori apps (Fiori elements, Smart Controls, adaptation projects)
Changing service bindings or entity sets
Communication Protocol

After implementing each Fiori-related component, briefly summarize what you did, e.g.:

“Updated XML view <ViewName>.view.xml to add a new sap.m.Input bound to /Name.”
“Added a press event handler in <ViewName>.controller.js and wired it to the button.”

Classify each change by impact level:

Small: Minor XML tweak, label text change, simple binding, simple event handler.
Medium: New UI section, new fragment, routing change, new model setup.
Large: New Fiori page (Object/Overview/List), major refactor of view/controller structure.

For Large changes, outline the Fiori implementation plan before coding:

Which views/controllers/fragments
Which models/entity sets
Which navigation pattern (e.g., List–Object)

Explicitly note:

Which UI features are completed (control added, binding wired, event handler implemented).
Which remain (e.g., error handling, value help, formatting) and are pending user confirmation.
Quality Assurance
Provide testable increments of the Fiori UI:
Clear where changes live: view/controller/manifest/i18n.
Minimal setup steps (e.g., “Run index.html with Component.js bootstrap” or “Start via FLP sandbox with tile X”).
Include usage examples for implemented components:
Example binding paths
Example event handler invocation (e.g., press flow)
Identify potential edge cases or limitations in the Fiori context:
Empty OData results / no data state
Long texts and wrapping
Responsive behavior (phone/tablet/desktop) only if explicitly requested
Suggest specific UI tests to verify correctness:
Control existence and type (sap.m.*, sap.f.*, Fiori elements sections)
Binding shows expected values
Events fire and perform the expected minimal actions
Navigation behaves as requested (if routing was in scope)
Balancing Efficiency with Control
For straightforward, low-risk Fiori tasks (e.g., adding a simple field, label, or button), you may implement the complete solution in one pass, still keeping it minimal.
For more complex Fiori modifications (new pages, complex table filters, multi-step navigation), break the work into:
View structure
Bindings
Controller logic
Navigation/config
When uncertain about Fiori scope (e.g., “Should this be a dialog or a new page?”, “Should I use Fiori elements or freestyle SAPUI5?”), pause and ask clarifying questions.
Adapt to the user’s preferred level of control:
More granular checkpoints for complex apps or highly controlled landscapes
Fewer checkpoints for small, isolated UI tweaks
Iterative Learning (SAP Fiori Context)
When you learn a new meaningful or key insight about:
The specific SAP Fiori app structure (views, controllers, components)
Custom architectural patterns (e.g., base controllers, shared models, helper utilities)
Non-obvious conventions (e.g., naming, routing patterns, common fragments)
Add it to memories under clear headings (e.g., “App Architecture”, “Routing Conventions”, “Shared Fragments”).
Keep this documentation concise; include only non-standard or non-obvious patterns that were hard to discover.
Review these memories frequently so you:
Reuse established Fiori patterns in this codebase
Avoid repeating mistakes or violating local conventions
Commit Statement Requirement
After each change set (even for small XML/controller edits), output a single concise commit message describing the Fiori/frontend change, for example:
feat: add customer name input field to header form
fix: correct table binding for sales orders list
refactor: move dialog fragment initialization to onInit

If you want, I can next distill this further into a very short checklist you can keep open in Windsurf specifically for Fiori work.