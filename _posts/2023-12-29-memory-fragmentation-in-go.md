---
layout: post
title: "Memory Fragmentation in Go"
date: 2023-12-29
---

Inspired by a seemingly unexplainable out of memory error in a service, I set out to understand how Go's non-moving memory management works under the hood. This led to some interesting learnings about memory fragmentation, the types of workloads that are prone to this issue, and potential mitigations.

### Memory Management

The Go runtime [source code](https://github.com/golang/go/blob/bbab863ada264642e2755f123ef3f84a6b3451d0/src/runtime/malloc.go) has good documentation on how memory management works. We will summarize a few of the relevant points here. At a high level, Go's memory allocator draws on ideas from `tcmalloc`. Small objects up to 32 KiB are rounded into [size classes](https://github.com/golang/go/blob/bbab863ada264642e2755f123ef3f84a6b3451d0/src/runtime/sizeclasses.go) and allocated on pages containing only objects of the same size class. Larger objects are directly allocated using runs of pages from the heap. If the heap does not have enough empty pages, a new group of pages will be requested from the operating system.

Go relies on garbage collection, but its GC is non-moving. This means that once an object is allocated, its memory address will not change[^gc-guide]. There are advantages to this memory management approach such as lower GC pause times. However, a non-moving GC cannot perform compaction like that of JVM[^jvm] and V8[^v8]. As a result, Go is more prone to memory fragmentation.

A background job in the Go runtime will occasionally look for pages that are no longer used and return them to the operating system through the `madvise` system call with a value of `MADV_DONTNEED`. This does not change the virtual memory range, but indicates to the operating system that the physical pages can be freed. The resident set size of the process is decreased accordingly.

### Measuring Fragmentation

Go provides accessible memory statistics through the `runtime.ReadMemStats` function. We are mostly interested in the `Heap*` variables. We describe two quantities that will be measured in later examples.

- `heapUsage`: This is the current heap usage from all used pages (including partially used pages that may contain as little as one small object). We compute this as `HeapSys - HeapReleased`. It does not capture all usage in the resident set size, but is a good proxy.
- `maxFragmentation`: This is the upper bound on memory fragmentation due to non-full pages. We compute this as `HeapInuse - HeapAlloc`. New objects of the right size class could fill some of the existing gaps and decrease fragmentation.

In a real application, it is more useful to have the upper bound percentage of fragmentation (measured as `maxFragmentation / heapUsage`) rather than absolute quantities. However, it is easier to track allocation groups in examples if we have exact memory usages.

### Setup

I'm running experiments in WSL 2 with Ubuntu 22.04.3 LTS. Experiments should be reproducible on any Linux-based systems running the same Go version, although there is some non-determinism due to the nature of garbage collection and OS interactions.

```shell
$ uname -r
4.19.128-microsoft-standard
$ go version
go version go1.21.3 linux/amd64
```

We show stubs for helper functions that will be used throughout the examples. There are some tricks that are necessary to get accurate measurements. In particular, Go will attempt to optimize out unused allocations and assignments (including assignments to `nil`), so we define an additional `Use` function that sets a global variable to prevent undesired optimizations.

```go
// Allocate returns a slice of the specified size where each entry is a pointer to a
// distinct allocated zero value for the type.
func Allocate[T any](n int) []*T

// Copy returns a new slice from the input slice obtained by picking out every n-th
// value between the start and stop as specified by the step.
func Copy[T any](slice []T, start int, stop int, step int) []T

// PrintMemoryStats prints out memory statistics after first running garbage 
// collection and returning as much memory to the operating system as possible.
func PrintMemoryStats()

// Use indicates the objects should not be optimized away.
func Use(objects ...any)
```

### Array of Pointers

We start with a simple example where we allocate a contiguous 16 MB slice of 16-byte objects (we use `[n]byte` to represent `n`-byte objects, but it could be replaced with a struct of the same size). We then hold a reference to a single object in that slice and lose the reference to the slice. As expected, at (3), the GC cannot collect the underlying array since it is still alive.

```go
func Example1() {
	PrintMemoryStats() // (1) heapUsage: 0.41 MiB, maxFragmentation: 0.24 MiB

	slice := make([][16]byte, 1<<20)
	Use(slice)

	PrintMemoryStats() // (2) heapUsage: 16.41 MiB, maxFragmentation: 0.24 MiB

	objectPtr := &slice[0]
	slice = nil
	Use(slice, objectPtr)

	PrintMemoryStats() // (3) heapUsage: 16.41 MiB, maxFragmentation: 0.24 MiB

	objectPtr = nil
	Use(slice, objectPtr)

	PrintMemoryStats() // (4) heapUsage: 0.41 MiB, maxFragmentation: 0.24 MiB

	Use(slice, objectPtr)
}
```

Instead of putting all objects contiguously, we could instead allocate each object individually and use an array of pointers. This allows us to hold references to individual objects without keeping the underlying array alive. In the example below, we allocate 16 MiB of 16-byte objects individually. Note that this does require an additional 8 MiB for the array of pointers. Unlike the previous example, holding a pointer to an object no longer keeps the array alive at (3).

```go
func Example2() {
	PrintMemoryStats() // (1) heapUsage: 0.44 MiB, maxFragmentation: 0.27 MiB

	slice := Allocate[[16]byte](1 << 20)
	Use(slice)

	PrintMemoryStats() // (2) heapUsage: 24.44 MiB, maxFragmentation: 0.26 MiB

	objectPtr := slice[0]
	slice = nil
	Use(objectPtr, slice)

	PrintMemoryStats() // (3) heapUsage: 0.45 MiB, maxFragmentation: 0.27 MiB
}
```

### Pathological Scenario

Let's continue with the array of pointers example. However, instead of keeping only one object alive, we will keep every 512th object alive (more on why later). This should only result in 2,048 objects being kept alive, or around 32 KiB. However, the actual memory usage is fairly surprising.

```go
func Example3() {
	PrintMemoryStats() // (1) heapUsage: 0.41 MiB, maxFragmentation: 0.25 MiB

	slice := Allocate[[16]byte](1 << 20)
	Use(slice)

	PrintMemoryStats() // (2) heapUsage: 24.41 MiB, maxFragmentation: 0.24 MiB

	badSlice := Copy(slice, 0, len(slice), 1024)
	slice = nil
	Use(slice, badSlice)

	PrintMemoryStats() // (3) heapUsage: 16.41 MiB, maxFragmentation: 16.19 MiB

	newSlice := Allocate[[32]byte](1 << 19)
	Use(slice, badSlice, newSlice)

	PrintMemoryStats() // (4) heapUsage: 36.39 MiB, maxFragmentation: 16.17 MiB

	Use(slice, badSlice, newSlice)
}
```

At (2), we do expect an additional 24 MiB of heap usage (16 MiB for objects and 8 MiB for the array of pointers). It seems that at (3), the heap usage should return to around the baseline level since both the slice and most of the objects are no longer alive. However, this is not the case. Instead, we see that heap usage only goes down by 8 MiB while the max fragmentation increases by 16 MiB. It turns out that most pages are only holding a single 16-byte object each.

As mentioned before, Go manages memory in pages and has a non-moving GC. Each internal page is 8 KiB. In this case, a page will fit exactly 512 16-byte objects. Objects of the same size class that are allocated around the same time will be placed on the same pages assuming that there are no existing pages for that size class. As a result, holding a reference to every 512th object is a pathological case that maximizes fragmentation. We repeat the experiment up to (3) but with differing step values to show that fragmentation is indeed highest at the chosen value.

| step | heapUsage (-baseline) | maxFragmentation (-baseline) |
|:----:|:---------------------:|:----------------------------:|
|  128 |       16.07 MiB       |           15.88 MiB          |
|  256 |       16.03 MiB       |           15.94 MiB          |
|  512 |       16.00 MiB       |           15.94 MiB          |
| 1024 |        8.04 MiB       |           8.00 MiB           |
| 2048 |        4.03 MiB       |           3.99 MiB           |

At (4), we see that a new allocation of 16 MiB of 32-byte objects (which are in a different size class) cannot use most of the existing pages containing fragmented space. As a result, the peak heap usage hovers at around 36 MiB instead of at around 20 MiB if there was no fragmentation. Note that there is a [special case](https://github.com/golang/go/blob/bbab863ada264642e2755f123ef3f84a6b3451d0/src/runtime/malloc.go#L1032) for tiny allocations in Go that are less than 16 B. These allocations are managed as 16 B blocks and can reuse the same pages as objects in the 16 B size class.

### Avoiding Fragmentation

There are many ways to avoid fragmentation, but there is not a single ideal solution for all cases. It is good to assess the requirements of the workload and the constraints in place.

- Reduce the overall number of allocations in the application (e.g., use `[]T` instead of `[]*T`).
- Use a buffer pool to reduce the number of size classes that are needed[^vora] (e.g., allow smaller allocations to reuse existing larger chunks of memory in the application).
- Maintain temporal locality for allocations[^sakamoto] (e.g., minimize the time between when an object is allocated to when it is freed and allocate long-lived objects close together).
- Occasionally perform manual compaction by copying objects.

The last point warrants more discussion because I think it requires very little change to application logic compared to the alternatives. If we know that there are long-lived objects which have poor temporal locality and/or vary greatly in size classes, we can still reduce fragmentation by manually copying them occasionally. This effectively compacts the memory and allows these objects to better utilize existing pages that may be heavily fragmented.

```go
func Example4() {
	PrintMemoryStats() // (1) heapUsage: 0.41 MiB, maxFragmentation: 0.24 MiB

	slice := Allocate[[16]byte](1 << 20)
	Use(slice)

	badSlice := Copy(slice, 0, len(slice), 512)
	slice = nil
	Use(slice, badSlice)

	PrintMemoryStats() // (2) heapUsage: 16.42 MiB, maxFragmentation: 16.20 MiB

	for i := range badSlice {
		objectCopy := new([16]byte)
		*objectCopy = *badSlice[i]
		badSlice[i] = objectCopy
	}

	PrintMemoryStats() // (3) heapUsage: 0.47 MiB, maxFragmentation: 0.25 MiB

	Use(slice, badSlice)
}
```

In the example above, we have the same fragmentation issue as before. However, we show that after reallocating and copying all objects in the existing slice, fragmentation decreases back to baseline levels. This technique can be applied to more complex data structures provided that all nested pointers are reallocated. Note that compaction may need to be performed continually until all of the associated long-lived objects are freed. One approach is to amortize the cost of reallocations by compacting only when the number of  long-lived objects doubles (e.g., by looking at the length of the container slice). Using a timed-based approach also works, but requires more application-specific tuning.

### Real-World Example

There was a service that started running into out of memory issues after we added a long-running task that computed some aggregate statistics. However, it took a few hours for these issues to manifest after starting the task. A few application properties hinted at memory fragmentation as the root cause.

- The long-running task does not require that much total memory since it stored less than 1 KiB per entry. However, it did slowly accumulate small objects over multiple hours while processing on the order of 50,000 entries.
- The service was also serving other requests that involved fairly large bursts of object allocations because it ingested data and processed PDFs. It was not uncommon for a request to need on the order of 10 MiB in allocations that was then all freed once the request completed.
- The long-running task also had similar bursts of allocations for each entry, except some objects in these allocations are kept alive until the entire task finished.

Due to the pattern of memory allocations and slow accumulation of pointers over time, there was poor temporal consistency. As a result, fragmentation likely increased slowly over time until the service was no longer able to serve normal requests. The solution we ended up choosing here was to separate these workloads. The long-running task was moved to a separate service so that the main service only served fast requests without long-lived objects.

### References

[^gc-guide]: Go Authors (2023). [A Guide to the Go Garbage Collector](https://tip.golang.org/doc/gc-guide).
[^jvm]: Oracle Help Center (2023). [Garbage-First (G1) Garbage Collector](https://docs.oracle.com/en/java/javase/17/gctuning/garbage-first-g1-garbage-collector1.html#GUID-ED3AB6D3-FD9B-4447-9EDF-983ED2F7A573).
[^v8]: Marshall, Peter (2019). [Trash talk: the Orinoco garbage collector](https://v8.dev/blog/trash-talk).
[^vora]: Vora, Sanjay (2022). [Overcoming Go Lang’s memory problem](https://www.druva.com/blog/overcoming-go-langs-memory-problem).
[^sakamoto]: Sakamoto, Hiroki (2023). [Why I encountered Go memory fragmentation? How did I resolve it?](https://medium.com/@taisho6339/why-i-encountered-go-memory-fragmentation-how-did-i-resolve-it-8542afe16eee).