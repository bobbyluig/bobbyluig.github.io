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
- Switch: This node type is used to handle conditional behavior in a workflow. It accepts exactly one input primitive and does not output anything. The framework will match the primitive's value against each of the switch's case values and select an edge to traverse. Each switch is required to have a default case.

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
            "description": "Node 1",
            "outgoing_edge_id": "edge_1",
            "configuration": { /* ... */ },
        },
        /* ... */
    ],
    "switch_nodes": [
        {
            "id": "node_2",
            "description": "Node 2",
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

Static analysis can be performed on a workflow before it is published to minimize errors and unintended behavior. This is similar to what a compiler would do after transforming a program into a control-flow graph[^cfg]. However, a workflow in this language is effectively already a control-flow graph where nodes are basic blocks. We do not introspect the implementation of processors and panes since they can be arbitrarily complex. Not all of the analysis types described below are implemented in production, but they are still interesting to explore.

### Unset Inputs

One runtime error that can occur is when a node specifies an input primitive that has never been set in the session. Due to branching behavior introduced switches, it is also possible that only some paths to a node will leave an input primitive unset. To avoid these issues, we want to warn developers when a node has an input that is not guaranteed to have been set.

{% raw %}
<div class="mermaid">
flowchart LR
    Source([Source]) --> A["A():(p1)"]
    A --> B{{"B(p1):()"}}
    B --> C["C(p1):(p2)"]
    B --> D["D(p1):(p3)"]
    D --> E["E(p2):()"]
    C --> E
    E --> Sink([Sink])
</div>
{% endraw %}

In the example above, we show the input and output primitives for each node. `E` has a potentially unset input `p2` since there is a path going through node `D` from the source to `E` where `p2` is never set by any node. Using this observation, we can define a node `n` as having a potentially unset input `p` if there exists at least one path from the source to `n` where `p` is not the output of any nodes along that path.

For a given node `n` and input `p`, we can determine if that input is potentially unset by using depth-first search to identify a path from `n` back to the source in the transpose graph[^transpose] considering only nodes that do not output `p`. If such a path exists, then `p` is a potentially unset input for `n`, and the path is one example traversal where `p` will not be set. This approach is not particularly efficient if done for every node and input in the workflow.

Another approach is to use data-flow analysis[^data-flow] to determine the set of primitive that are guaranteed to be assigned before the entry point of every node. We can perform a forward analysis starting with the empty set at the source. We define a transfer function for each node where the exit set is the union of the entry set and the node's output primitives. We also define a meet operation that combines the exit sets of predecessors by computing their intersection. Potentially unset inputs can be determined by computing the set difference between a node's input primitives and the guaranteed-assigned primitives before the entry point of that node.

### Unused Outputs

A node can set an output primitive that will never be used by another node. This does not cause any runtime errors, but could indicate that the developer forgot to add new nodes or additional inputs to existing nodes. It is also possible to the output primitive of a node to be ineffective in that it will be overwritten by the output of another node prior to its first use. We want to avoid both of these cases because polluting the session state increases the likelihood of bugs.

{% raw %}
<div class="mermaid">
flowchart LR
    Source([Source]) --> A["A():(p1,p2)"]
    A --> B{{"B(p1):()"}}
    B --> C["C():(p2,p3)"]
    B --> D["D():(p2)"]
    C --> E["E(p2):()"]
    D --> E
    E --> Sink([Sink])
</div>
{% endraw %}

In the example above, `p3` is an unused since there are no nodes after `C` which has `p3` as an input. `p2` is also unused from `A` because it is overwritten by `C` and `D` prior to its first use in `E`. We define an output `p` as potentially used from node `n` if there is a path from `n` to the sink (assuming that the sink is always reachable from every node) where `p` is used as an input prior to reassignment.

We can use depth-first search starting from `n`. We ignore the successors of any nodes where `p` is set as an output since it would indicate that `p` is reassigned. If we encounter any node where `p` is used as an input, exit immediately because we know that `p` is potentially used. After the search terminates and has visited all reachable nodes starting from `n` without finding a node that uses `p`, we can assert that `p` is unused from `n`.

Data-flow analysis can also be used to determine the set of primitives that are potentially used after the exit point of each node. This is the same problem as live variable analysis[^liveness] with use/def of variables corresponding to inputs/outputs of nodes. Once the live variables are obtained for each node, unused outputs can be determined by computing the set difference between a node's output primitives and the potentially-used primitives after the exit point of that node.

### Unreachable Nodes

If a node is not reachable from the source, then it will never be executed and we should not include it in the workflow. This usually happens when new nodes are added to a workflow but are not connected to the remainder of the workflow correctly.

{% raw %}
<div class="mermaid">
flowchart LR
    Source([Source]) --> A
    A --> B
    C --> D
    D --> E{{E}}
    E --> B
    E --> C
    B --> Sink([Sink])
</div>
{% endraw %}

Unreachable nodes can be found by performing depth-first search starting from the source. All reachable nodes will be marked by the search. Any remaining nodes are guaranteed to be unreachable. In the example above, nodes `C`, `D`, and `E` are unreachable. Note that it is not enough to just validate that each node has an input edge since cycles are permitted.

We can do slightly better if we are able to prove that certain switch branches are never taken. However, due to the lack of node introspection, we can only assert basic properties such as whether a primitive is definitely not set. To do this, we can examine the transpose graph and use depth-first search to verify that no visited nodes output the given primitive.

### Infinite Loops

## Workflow Transpilation

## Refactoring with Subgraphs

## References

[^node-graph]: Wikipedia (2024). [Node graph architecture](https://en.wikipedia.org/wiki/Node_graph_architecture).
[^cfg]: University of Toronto (2017). [17.8 Application: Control Flow Graphs](https://www.teach.cs.toronto.edu/~csc110y/fall/notes/17-graphs/08-control-flow-graphs.html).
[^transpose]: Wikipedia (2024). [Transpose graph](https://en.wikipedia.org/wiki/Transpose_graph).
[^data-flow]: Carnegie Mellon University (2011). [Introduction to Data Flow Analysis](https://www.cs.cmu.edu/afs/cs/academic/class/15745-s11/public/lectures/L4-Intro-to-Dataflow.pdf).
[^liveness]: Cornell University (2022). [Live Variable Analysis](https://www.cs.cornell.edu/courses/cs4120/2022sp/notes.html?id=livevar).