package main

import (
	"fmt"
	"runtime"
	"runtime/debug"
)

// noOptimize is a variable to prevent the compiler from fully optimizing away variables.
var noOptimize any

// Allocate returns a slice of the specified size where each entry is a pointer to a distinct
// allocated zero value for the type.
func Allocate[T any](n int) []*T {
	data := make([]*T, n)

	for i := range data {
		data[i] = new(T)
	}

	return data
}

// Copy returns a new slice from the input slice obtained by picking out every n-th value between
// the start and stop as specified by the step.
func Copy[T any](slice []T, start int, stop int, step int) []T {
	data := make([]T, (stop-start)/step)

	for i := range data {
		data[i] = slice[start+i*step]
	}

	return data
}

// Use indicates the objects should not be optimized away.
// go:noinline
func Use(objects ...any) {
	noOptimize = objects
}

// ToMebibytes converts bytes to mebibytes.
func ToMebibytes(bytes uint64) float64 {
	return float64(bytes) / (1 << 20)
}

// PrintMemoryStats prints out memory statistics after first running garbage collection and
// returning as much memory to the operation system as possible.
// go:noinline
func PrintMemoryStats() {
	runtime.GC()
	debug.FreeOSMemory()

	var m runtime.MemStats
	runtime.ReadMemStats(&m)
	fmt.Printf(
		"heapUsage: %.2f MiB, maxFragmentation: %.2f MiB\n",
		ToMebibytes(m.HeapSys-m.HeapReleased),
		ToMebibytes(m.HeapInuse-m.HeapAlloc),
	)
}

func Example1() {
	PrintMemoryStats()

	slice := make([][16]byte, 1<<20)
	Use(slice)

	PrintMemoryStats()

	objectPtr := &slice[0]
	slice = nil
	Use(objectPtr, slice)

	PrintMemoryStats()

	objectPtr = nil
	Use(objectPtr)

	PrintMemoryStats()
}

func Example2() {
	PrintMemoryStats()

	array := Allocate[[16]byte](1 << 20)
	Use(array)

	PrintMemoryStats()

	objectPtr := array[0]
	array = nil
	Use(objectPtr, array)

	PrintMemoryStats()
}

func Example3() {

	PrintMemoryStats()

	array := Allocate[[16]byte](1 << 20)
	Use(array)

	PrintMemoryStats()

	badArray := Copy(array, 0, len(array), 512)
	array = nil
	Use(badArray, array)

	PrintMemoryStats()

	newArray := Allocate[[32]byte](1 << 19)
	Use(badArray, newArray)

	PrintMemoryStats()
}

func Example4() {
	PrintMemoryStats()

	array := Allocate[[16]byte](1 << 20)
	Use(array)

	goodArray := Copy(array, 0, len(array), 512)
	array = nil
	Use(goodArray, array)

	PrintMemoryStats()
}

func Example5() {
	PrintMemoryStats()

	array := Allocate[[16]byte](1 << 20)
	Use(array)

	badArray := Copy(array, 0, len(array), 512)
	array = nil
	Use(badArray, array)

	goodArray := make([]*[16]byte, len(badArray))
	for i := range goodArray {
		goodArray[i] = new([16]byte)
		*goodArray[i] = *badArray[i]
	}
	badArray = nil
	Use(badArray, goodArray)

	PrintMemoryStats()
}

func main() {
	Example1()
}
