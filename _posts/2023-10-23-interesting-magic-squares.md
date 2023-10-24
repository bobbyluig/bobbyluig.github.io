---
layout: post
title: "Interesting Magic Squares"
date: 2023-10-23
---

Earlier this year, I visited Barcelona for the first time and saw the magic square on the Sagrada Familia. Unlike a normal 4×4 magic square, this one has a magic constant of 33 and a total of 310 combinations that add up to the magic constant. I wanted to know if there were other magic squares that had even more interesting properties given similar constraints.

## Trivial and Non-normal

We'll start with the definition of magic squares for Wikipedia. There are stricter definitions of magic squares, but we want one that includes the magic square on the Sagrada Familia. 

> "In recreational mathematics, a square array of numbers, usually positive integers, is called a magic square if the sums of the numbers in each row, each column, and both main diagonals are the same."  
> — Magic square, Wikipedia[^wikipedia]

A normal $$n \times n$$ magic square consists of all integers in $$[1, n^2]$$. In order for a non-normal 4×4 magic square to sum to 33, there must be at least one repeating number if we require the square to only contain positive integers. This is because a normal 4×4 magic square has a magic constant of 34, so any magic constant less than that requires a smaller total sum for all numbers in the square.

$$
\begin{bmatrix}
1 & 14 & 14 & 4 \\
11 & 7 & 6 & 9 \\
8 & 10 & 10 & 5 \\
13 & 2 & 3 & 15 
\end{bmatrix}
$$

As seen above, the Sagrada Familia magic square has two repeating numbers, 10 and 14. This makes it trivial. However, we know that the magic constant of 33 makes it impossible to have a non-trivial magic square. If we relax the positive integer constraint and allow zeros, then it is possible to create non-trivial examples. Lee Sallows presents a few, along with a harsh critique of the architect (due to the triviality of the magic square composition).

$$
\begin{bmatrix}
0 & 2 & 17 & 14 \\
6 & 15 & 7 & 5 \\
18 & 3 & 8 & 4 \\
9 & 13 & 1 & 10 
\end{bmatrix}

\begin{bmatrix}
0 & 2 & 14 & 17 \\
16 & 13 & 3 & 1 \\
12 & 8 & 9 & 4 \\
5 & 10 & 7 & 11 
\end{bmatrix}

\begin{bmatrix}
0 & 5 & 12 & 16 \\
15 & 11 & 6 & 1 \\
10 & 3 & 13 & 7 \\
8 & 14 & 2 & 9 
\end{bmatrix}
$$

> "The true significance of the Sagrada Familia magic square is thus that it is a monumental blunder: Subirachs has immortalized his nescience in stone."  
> — Lee Sallows, The Mathematical Intelligencer[^sallows]

## Generating Squares

There are $$16!$$ ways to permute distinct numbers in a 4×4 square, although most of them will not satisfy the criteria for a magic square. Hjort outlines a strategy to generate magic squares based on Markov chains by starting with an initial set of numbers, randomly permuting pairs of them, and accepting or rejecting the resulting proposals based on some probabilistic criteria[^hjort].

The criteria relies on an error function that approaches zero as the square approaches a desired one (i.e., a square where the rows, columns, and main diagonals sum to the magic constant). We show an example error function $$E(x)$$ below.

$$
\begin{aligned}
E(x) &= \sum_{i=1}^{4} \left|\sum_{j=1}^{4} x\left[i,j\right] - 33\right| + \sum_{j=1}^{4} \left|\sum_{i=1}^{4} x\left[i,j\right] - 33\right| \\
&+ \sum_{i=1}^{4} \left|x\left[i,i\right] - 33\right| + \sum_{i=1}^{4} \left|x\left[i,5-i\right] - 33\right|
\end{aligned}
$$

Note that while it is possible to generate normal magic squares using existing algorithms[^moler], we will instead focus on finding non-normal magic squares where the error function is more complex than the provided example and not easily minimized through linear algebra.

### Simple Algorithm

In practice, I found that a slightly simpler algorithm can also be used to quickly generate valid squares. The two main differences to Hjort's approach are that we will only perturb individual elements in a square and accept proposals using a deterministic criteria. Note that this does not preserve the set of numbers in the initial square, but works well if we are just searching for squares that minimize $$E(x)$$.

1. Generate a 4×4 square $$x$$ where each value is uniformly chosen from $$[1, 30]$$. There is no need to try higher numbers since those cannot result in valid squares.
2. Compute $$E(x)$$. If it is zero, we are done and have found a valid square.
3. Attempt all possible single location perturbations in a random order until we find some $$x^\prime$$ such that $$E(x^\prime) < E(x)$$. Each perturbation involves replacing the value at a location to a different one from $$[1, 30]$$. If no such $$x^\prime$$ exists, return to step 1. Otherwise, let $$x = x^\prime$$ and return to step 2.

A key insight is that at some point, it may no longer be possible to decrease $$E(x)$$ by just changing a single number. In that case, we can restart instead of trying to climb out of the local minima. This algorithm is similar to stochastic gradient descent if we view each element in the square as a parameter to minimizing the objective function $$E(x)$$.

### Efficient Permutations

The reason we want to attempt all possible single location perturbations in a random order instead of some fixed order is so that the resulting squares are not biased towards a specific pattern imposed by the ordering. However, materializing the permutations of locations and the permutations of numbers to try for each location is quite wasteful since we do not expect to need all perturbations before finding a better square. 

Instead, we can design an iterator that takes constant time to advance through a permutation and constant time to reset regardless of the size of the permuted set. It relies on the Fisher–Yates shuffle subroutine, except it only does one swap every time the iterator is advanced. Resetting the iterator can be done by leaving the partially shuffled array as is, and restarting the pointer at the beginning of the array. An implementation in Go is shown below.

```go
type Permutation[T any] struct {
	index int
	slice []T
	rng   *rand.Rand
}

func NewPermutation[T any](rng *rand.Rand, slice []T) *Permutation[T] {
	return &Permutation[T]{
		index: 0,
		slice: slice,
		rng:   rng,
	}
}

func (p *Permutation[T]) Next() bool {
	if p.index >= len(p.slice) {
		p.Reset()
		return false
	}

	swapIndex := p.rng.Intn(len(p.slice)-p.index) + p.index
	p.slice[p.index], p.slice[swapIndex] = p.slice[swapIndex], p.slice[p.index]
	p.index++
	return true
}

func (p *Permutation[T]) Reset() {
	p.index = 0
}

func (p *Permutation[T]) Get() T {
	return p.slice[p.index-1]
}
```

## Interesting Criteria

Now that we know how to generate magic squares, we can focus on what makes a magic square interesting. This is fairly subjective, but I wanted to focus on three aspects in order of importance: unique numbers, symmetrical groups, and combinations.

Although all positive magic squares with a magic constant of 33 are trivial, some are more trivial than others. We want to find magic squares that have the minimum number of duplicates. In this case, the desired magic squares should have only one number duplicated. We can encode this into the error function by adding in $$(\operatorname{card}(x) - 15)$$.

A second property that makes magic squares interesting is the number of groups that have symmetrical pairs (including itself) and add up to the magic constant. We define symmetry as a reflection across the x-axis, y-axis, or both. Below are three example groups in the Sagrada Familia magic square that have symmetry of the respective types[^sagrada-familia]. Note that by definition, all rows, columns, and major diagonals in any magic square are symmetrical groups.

$$
\begin{bmatrix}
1 & 14 & 14 & \color{BurntOrange}{4} \\
11 & \color{NavyBlue}{7} &  \color{NavyBlue}{6} & \color{BurntOrange}{9} \\
8 & \color{BurntOrange}{10} & \color{BurntOrange}{10} &  \color{NavyBlue}{5} \\
13 & 2 & 3 & \color{NavyBlue}{15} 
\end{bmatrix}

\begin{bmatrix}
1 & 14 & 14 & 4 \\
11 & \color{BurntOrange}{7} & \color{NavyBlue}{6} & 9 \\
8 & \color{BurntOrange}{10} & \color{NavyBlue}{10} & 5 \\
\color{BurntOrange}{13} & \color{NavyBlue}{2} & \color{BurntOrange}{3} & \color{NavyBlue}{15}
\end{bmatrix}

\begin{bmatrix}
\color{BurntOrange}{1} & 14 & \color{BurntOrange}{14} & 4 \\
11 & \color{NavyBlue}{7} & 6 & \color{NavyBlue}{9} \\
\color{BurntOrange}{8} & 10 & \color{BurntOrange}{10} & 5 \\
13 & \color{NavyBlue}{2} & 3 & \color{NavyBlue}{15} 
\end{bmatrix}
$$

We want to find squares that have a lot of symmetrical groups, but this computation	is fairly expensive since we need to examine all potential groups for every perturbation. Instead of incorporating this into the error function, we first generate valid squares that only contain one duplicate and then calculate the number of symmetrical groups.

Lastly, we want to maximize the number of combinations that add up to the magic constant. This is only a function of the elements within the square and does not depend on how they are placed. Similar to symmetrical groups, we compute this after first generating a valid square. 

## Results

After generating around 100 million candidate squares, I found some very interesting ones. These are not necessarily the most interesting squares according to our criteria, but they were the best ones that the program produced after a few minutes. Out of curiosity, I also searched for interesting squares without any duplicates but allowing zero as a value. The results are shown below.

$$
\begin{bmatrix}
4 & 6 & 7 & 16 \\
10 & 9 & 11 & 3 \\
18 & 5 & 8 & 2 \\
1 & 13 & 7 & 12 \\
\end{bmatrix}

\begin{bmatrix}
2 & 7 & 15 & 9 \\
21 & 3 & 8 & 1 \\
6 & 12 & 10 & 5 \\
4 & 11 & 0 & 18 \\
\end{bmatrix}
$$

The left square has 1 duplicate, 55 symmetrical groups, and 327 combinations. The right square has 0 duplicates, 54 symmetrical groups, and 378 combinations. For comparison, the magic square on the Sagrada Familia has 2 duplicates, 45 symmetrical groups, and 310 combinations.

## References

[^wikipedia]: Wikipedia (2023). [Magic square](https://en.wikipedia.org/wiki/Magic_square).
[^sallows]: Sallows, Lee (2003). [Letters: The Mathematical Intelligencer](https://link.springer.com/article/10.1007/BF02984856).
[^hjort]: Hjort, Nils Lid (2019). [The Magic Square of 33](https://www.mn.uio.no/math/english/research/projects/focustat/the-focustat-blog!/gaudisquare.html).
[^moler]: Moler, Cleve (2012). [Magic Squares, Part 2, Algorithms](https://blogs.mathworks.com/cleve/2012/11/05/magic-squares-part-2-algorithms/).
[^sagrada-familia]: Sagrada Familia (2018). [The magic square on the Passion façade: keys to understanding it](https://blog.sagradafamilia.org/en/divulgation/the-magic-square-the-passion-facade-keys-to-understanding-it/).