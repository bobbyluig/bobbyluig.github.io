---
layout: post
title: "Memory Fragmentation in Go"
date: 2023-12-28
---

TODO

### TODO

```go
// Allocate returns a slice of the specified size where each entry is a pointer to a
// distinct allocated zero value for the type.
func Allocate[T any](n int) []*T

// Copy returns a new slice from the input slice obtained by picking out every n-th
// value between the start and stop as specified by the step.
func Copy[T any](slice []T, start int, stop int, step int) []T

// PrintMemoryStats prints out memory statistics after first running garbage 
// collection and returning as much memory to the operation system as possible.
func PrintMemoryStats()

// Use indicates the objects should not be optimized away.
func Use(objects ...any)
```
