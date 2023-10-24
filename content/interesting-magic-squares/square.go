package main

import (
	"fmt"
	"math"
	"math/bits"
	"math/rand"
	"sort"
	"strconv"
	"strings"
	"sync"

	"gonum.org/v1/gonum/stat/combin"
)

var masks [][16]int
var slices [][]int
var combinationSlices [][]int
var flipX []int
var flipY []int

func init() {
	masks = [][16]int{
		{
			1, 1, 1, 1,
			2, 2, 2, 2,
			3, 3, 3, 3,
			4, 4, 4, 4,
		},
		{
			1, 2, 3, 4,
			1, 2, 3, 4,
			1, 2, 3, 4,
			1, 2, 3, 4,
		},
		{
			1, 0, 0, 2,
			0, 1, 2, 0,
			0, 2, 1, 0,
			2, 0, 0, 1,
		},
		// {
		// 	1, 1, 2, 2,
		// 	1, 1, 2, 2,
		// 	3, 3, 4, 4,
		// 	3, 3, 4, 4,
		// },
		// {
		// 	2, 4, 3, 1,
		// 	4, 2, 1, 3,
		// 	3, 1, 2, 4,
		// 	1, 3, 4, 2,
		// },
		// {
		// 	2, 3, 3, 2,
		// 	4, 1, 1, 4,
		// 	4, 1, 1, 4,
		// 	2, 3, 3, 2,
		// },
		// {
		// 	1, 1, 2, 2,
		// 	3, 3, 4, 4,
		// 	4, 4, 3, 3,
		// 	2, 2, 1, 1,
		// },
		// {
		// 	1, 1, 4, 4,
		// 	2, 2, 3, 3,
		// 	1, 1, 4, 4,
		// 	2, 2, 3, 3,
		// },
		// {
		// 	2, 1, 2, 1,
		// 	3, 4, 3, 4,
		// 	2, 1, 2, 1,
		// 	3, 4, 3, 4,
		// },
	}

	for k := 2; k <= 15; k++ {
		combinationSlices = append(combinationSlices, combin.Combinations(16, k)...)
	}

	for _, mask := range masks {
		maskSlices := make([][]int, 16)
		for i := 0; i < 16; i++ {
			if mask[i] > 0 {
				maskSlices[mask[i]] = append(maskSlices[mask[i]], i)
			}

		}
		for _, maskSlice := range maskSlices {
			if len(maskSlice) > 0 {
				slices = append(slices, maskSlice)
			}
		}
	}

	flipX = []int{
		12, 13, 14, 15,
		8, 9, 10, 11,
		4, 5, 6, 7,
		0, 1, 2, 3,
	}
	flipY = []int{
		3, 2, 1, 0,
		7, 6, 5, 4,
		11, 10, 9, 8,
		15, 14, 13, 12,
	}
}

func sliceError(square [16]int, slice []int) float64 {
	sum := 0
	for _, index := range slice {
		sum += square[index]
	}
	return math.Abs(float64(sum) - 33.0)
}

func slicesError(square [16]int, slices [][]int) float64 {
	sum := 0.0
	for _, slice := range slices {
		sum += sliceError(square, slice)
	}
	return sum
}

func uniqueError(square [16]int) float64 {
	var bitSet uint64
	for _, value := range square {
		bitSet |= 1 << value
	}
	return 15.0 - float64(bits.OnesCount64(bitSet))
}

func combinations(square [16]int) int {
	count := 0
	for _, slice := range combinationSlices {
		if sliceError(square, slice) == 0 {
			count++
		}
	}
	return count
}

func symmetryPairs(square [16]int) int {
	sliceToKey := func(slice []int) string {
		copySlice := make([]int, len(slice))
		copy(copySlice, slice)
		sort.Ints(copySlice)
		b := make([]string, len(slice))
		for i, v := range copySlice {
			b[i] = strconv.Itoa(v)
		}
		return strings.Join(b, ",")
	}

	sliceFlip := func(slice []int, flipMap []int) []int {
		out := make([]int, len(slice))
		for i, v := range slice {
			out[i] = flipMap[v]
		}
		return out
	}

	slicesSet := map[string]struct{}{}

	for _, slice := range combinationSlices {
		sliceKey := sliceToKey(slice)

		if _, ok := slicesSet[sliceKey]; ok {
			continue
		}

		if sliceError(square, slice) == 0.0 {
			flipXSlice := sliceFlip(slice, flipX)
			flipYSlice := sliceFlip(slice, flipY)

			if sliceError(square, flipXSlice) == 0.0 {
				slicesSet[sliceToKey(flipXSlice)] = struct{}{}
			}
			if sliceError(square, flipYSlice) == 0.0 {
				slicesSet[sliceToKey(flipYSlice)] = struct{}{}
			}
		}
	}

	return len(slicesSet)
}

func totalError(square [16]int) float64 {
	return slicesError(square, slices) +
		uniqueError(square)
}

type permutation struct {
	index int
	slice []int
	rng   *rand.Rand
}

func newPermutation(rng *rand.Rand, slice []int) *permutation {
	return &permutation{
		index: 0,
		slice: slice,
		rng:   rng,
	}
}

func (p *permutation) next() bool {
	if p.index >= len(p.slice) {
		p.reset()
		return false
	}

	swapIndex := p.rng.Intn(len(p.slice)-p.index) + p.index
	p.slice[p.index], p.slice[swapIndex] = p.slice[swapIndex], p.slice[p.index]
	p.index++
	return true
}

func (p *permutation) reset() {
	p.index = 0
}

func (p *permutation) get() int {
	return p.slice[p.index-1]
}

func makeRange(min int, max int) []int {
	slice := make([]int, max-min)
	for i := range slice {
		slice[i] = min + i
	}
	return slice
}

func randomValue(r *rand.Rand) int {
	return 1 + r.Intn(30)
}

func randomSquare(r *rand.Rand) [16]int {
	var square [16]int
	for i := range square {
		square[i] = randomValue(r)
	}
	return square
}

func bestSquare(r *rand.Rand) [16]int {
	square := randomSquare(r)
	minError := math.Inf(1)

	indexP := newPermutation(r, makeRange(0, 16))
	valueP := newPermutation(r, makeRange(1, 18))

	tryImprove := func() bool {

		for indexP.next() {
			index := indexP.get()
			oldValue := square[index]

			for valueP.next() {
				square[index] = valueP.get()

				e := totalError(square)
				if e < minError {
					minError = e
					return true
				} else {
					square[index] = oldValue
				}
			}
		}

		return false
	}

	for tryImprove() {
		indexP.reset()
		valueP.reset()
	}

	return square
}

func findSquare(mu *sync.Mutex, best *int) {
	r := rand.New(rand.NewSource(rand.Int63()))
	for i := 0; i < 1000000; i++ {
		square := bestSquare(r)
		if e := totalError(square); e == 0 {
			sN := symmetryPairs(square)
			mu.Lock()
			if sN > *best {
				*best = sN
				fmt.Printf("%f, %d, %d, %v\n", e, combinations(square), sN, square)
			}
			mu.Unlock()
		}
	}
}

func main() {
	original := [16]int{1, 14, 14, 4, 11, 7, 6, 9, 8, 10, 10, 5, 13, 2, 3, 15}
	fmt.Println(totalError(original))
	fmt.Println(combinations(original))
	fmt.Println(symmetryPairs(original))

	var best int
	var mu sync.Mutex
	var wg sync.WaitGroup

	for i := 0; i < 10; i++ {
		wg.Add(1)
		go func() {
			findSquare(&mu, &best)
			wg.Done()
		}()
	}

	wg.Wait()
}

// 0.000000, 327, 55, [4 6 7 16 10 9 11 3 18 5 8 2 1 13 7 12]
// 0.000000, 364, 53, [17 0 6 10 2 8 4 19 9 14 7 3 5 11 16 1]
