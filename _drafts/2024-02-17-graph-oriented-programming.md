---
layout: post
title: "Graph-Oriented Programming"
date: 2024-02-17
features: [highlight, mathjax, mermaid]
---

I have recently been developing with a graph-based domain-specific language at work that powers most of the user onboarding flows. It was created in-house and has evolved over the years. I wanted to share some interesting learnings about the language itself as well as improvements that we made to improve developer efficiency and language safety.

## Language and Framework

The domain-specific language was designed to facilitate building workflows in a visual manner. In a user onboarding flow, there are various sequential steps that the user must go through. For example, we may first show the user a screen to enter their phone number. Once they do that, we run some logic behind the scenes to generate and send a one-time password. Then, we present the user with a screen to input the one-time password that they received.

{% raw %}
<div class="mermaid">
flowchart LR
    Source([Source]) --> Pane[/Pane/]
    Pane --> Processor[Processor]
    Processor --> Switch{{Switch}}
    Switch -->|Case 1| Pane
    Switch -->|Case 2| Sink([Sink])
</div>
{% endraw %}

The diagram above shows a very simple workflow that contains the main nodes types in the language. A workflow is a directed but not necessarily acyclic graph starting from a single source node and ending at one or more sink nodes. The framework is responsible for interpreting the workflow and maintaining state for sessions. Each traversal of the graph represents a unique session, and state between workflow sessions are kept separate. However, nodes are free to interact with other services to manipulate global system state outside of the workflow.

Some nodes can read or write to session state through predefined primitives, which are just protocol buffer object types. Each type effectively operates as a unique variable name. The framework handles populating input primitives before invoking a node and updating the workflow state based on a node's output primitives. This does require that nodes specify input and output primitives, but this is similar to defining the signature for a function.

 We describe each of the node types in more detail.

- Pane: This node type is used to display information to users or retrieve user input. It allows zero or more input and output primitives. Generally, a pane can read global system state but not mutate it. All outputs should be written to the session state.
- Processor: This node type is used to run arbitrary business logic. It allows zero or more input and output primitives. A processor can mutate global system state (e.g., performing database writes) in addition to the session state.
- Sink: This is a special node type that indicates to the framework that a workflow is complete. There may be more than one sink node with different designations to indicate to the framework what type of exit was taken.
- Source: This is a special node type that is used to mark the start of the workflow. The framework will always begin executing a workflow form the source node.
- Switch: This node type is used to handle conditional behavior in a workflow. It accepts exactly one input primitive and does not output anything. The framework will match the primitive's value against each of the switch's case values and select an edge to traverse.

Workflow are stored in JSON format. An example is shown below. However, while this representation is easy for the framework to load and interpret, it is fairly difficult for developers to edit directly. Instead, we rely on a visual workflow editor that converts the JSON to a graph representation and allows developers to work through the visual representation instead. 

```json
{
    "edges": [
        {
            "id": "edge_1",
            "from_node_id": "node_1",
            "to_node_id": "node_2",
        },
        /* ... */
    ],
    "processor_nodes": [
        {
            "id": "node_1",
            "outgoing_edge_id": "edge_1",
            "configuration": { /* ... */ }
        },
        /* ... */
    ],
    "switch_nodes": [
        {
            "id": "node_2",
            "condition_primitive": { /* ... */ },
            "cases": [
                {
                    "value": 1,
                    "outgoing_edge_id": "edge_2",
                },
                /* ... */
            ]
        },
        /* ... */
    ]
}
```

At a high level, the language draws on inspirations from the node graph architecture[^node-graph]. However, it is not designed to be a low-code development workflow since many changes involve altering the underlying implementations of processors and panes. The graph representation enforces abstraction in the form of nodes, but also has various drawbacks that we will discuss in later sections.

## Static Analysis

## Workflow Transpilation

## Refactoring with Subgraphs

## References

[^node-graph]: Wikipedia (2024). [Node graph architecture](https://en.wikipedia.org/wiki/Node_graph_architecture).