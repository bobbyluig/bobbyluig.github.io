---
layout: post
title: "Interesting Magic Squares"
date: 2023-09-26
---

Earlier this year, I visited Barcelona for the first time and saw the magic square on the Sagrada Família. Unlike a normal 4×4 magic square, this one has a magic constant of 33 and a total of 310 combinations that add up to the magic constant. I wanted to know if there other magic squares that had even more interesting properties given similar constraints.

## Trivial and Non-normal

We'll start with the definition of magic squares for Wikipedia. There are stricter definitions of magic squares, but we want one that includes the magic square on the Sagrada Família. 

> "In recreational mathematics, a square array of numbers, usually positive integers, is called a magic square if the sums of the numbers in each row, each column, and both main diagonals are the same."  
> — Magic square, Wikipedia 

A normal $$n \times n$$ magic square consists of all integers in $$[1, n^2]$$. In order for a non-normal 4×4 magic square to sum to 33, there must be at least one repeating number if we require the square to only contain positive integers. This is because a normal 4×4 magic square has a magic constant of 34, so any magic constant less than that requires repeating numbers.

$$
\begin{bmatrix}
1 & 14 & 14 & 4 \\
11 & 7 & 6 & 9 \\
8 & 10 & 10 & 5 \\
13 & 2 & 3 & 15 
\end{bmatrix}
$$

As seen above, the Sagrada Família magic square has two repeating numbers, 10 and 14. This makes it trivial. However, we know that the magic constant of 33 makes it impossible to have a non-trivial magic square. If we relax the positive integer constraint and allow zeros, then it is possible to create non-trivial examples. Lee Sallows presents a few, along with a harsh critique of the architect (due to the triviality of the magic square composition).

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

> "The true signiﬁcance of the Sagrada Familia magic square is thus that it is a monumenal blunder: Subirachs has immortalized his nescience in stone."  
> — Lee Sallows, The Mathematical Intelligencer
