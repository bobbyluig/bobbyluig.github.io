---
layout: post
title: "Compressing Sentry Ownership Rules"
date: 2023-12-17
---

I had to solve a fun problem at work related to Sentry's ownership rules because my changes put us over the character limit. It felt very much like an interview problem. However, I think the ideal implementation is not one which has the optimal time complexity or compression ratio.

## Background

For a given project, Sentry allows you to define a set of ownership rules to automatically route issues to appropriate teams based on matcher types such as file paths and tags. We use this feature extensively in our API service because while the platform is owned by one team, product routes and logic are owned by various teams across the company.

Simplifying a bit, we have an internal CLI tool that engineers can manually run to generate ownership rules for Sentry based on metadata in our repository that defines team ownership for file paths and routes. The rules mapped each individual file path and route in the API service to an owner without any compression. An condensed example is shown below.

```
path:*/routes/asset/asset_report_create.go #team-assets
path:*/routes/asset/asset_report_get.go #team-assets
path:*/routes/asset/asset_report_pdf_get.go #team-assets
# ...
path:*/routes/investments/investment_holdings_get.go #team-investments
path:*/routes/investments/investment_transactions_get.go #team-investments
```

One day, I noticed that some alerts for a different team were incorrectly routed to us, and traced the root cause to a missing set of rules. It turned out that we had hard coded a set of route rules in the preamble instead of generating them like we do for file paths. Therefore, I modified the CLI tool to generate a set of rules based on `tags.request_route_string`, which is the tag that we emitted for the route of a Sentry event. Unfortunately, this put us over the 100k characters limit for Sentry ownership rules.

## Finding a Solution

The 100k character limit seemed pretty arbitrary, and while we did joke about it, we ultimately decided it was probably best to not ask Sentry if they can increase this limit since the documentation was pretty clear on what to do in this scenario.

> "We support ownership rules with up to 100,000 characters. If your rule exceeds this size, we suggest using wildcard rules to consolidate multiple entries into one."  
> — Ownership Rules, Sentry Documentation[^sentry]

I do think a good alternative is to redesign our middleware to always emit something like `tags.owner` (which we already do in some cases) by analyzing properties of an error at runtime within our systems before emitting them to Sentry. This would allow us to drastically simplify ownership rules. However, this is a longer-term solution because it would require service changes and extensive testing to validate that events would be routed to the same team.

We decided that the best short-term solution was to follow Sentry's recommendation and attempt to compress the ownership rules using wildcards. We could then easily verify whether the compressed output was correct by running each file path and route through both sets of rules.

## Rule Compression

There were a few key observations that guided the algorithm for compressing rules.

- The compressed rules should be human readable and be sensible for someone looking at how an event was routed to their team.
- Most team ownership could be grouped into prefixes, but there were exceptions to this (e.g., each file in a directory is owned by a different team).
- Even when the rules are slightly out of date, routing should still be reasonable for new file paths and routes under existing prefixes.

To make rules easy to understand, we want the compressed output to be unambiguous in the sense that a prefix should not belong to more than one team. Although this doesn't achieve the best compression ratio, it makes it clear for someone looking at the rules how a particular routing decision was made. We also would prefer `*/routes/asset*` over `*/routes/a*` even if both of them are unambiguous  for the given input because complete words are easier to understand and should result in better routings of new file paths and routes.

The algorithm we decided to implement is as follows. For each rule that is not yet compressed, find the shortest valid prefix that results in an unambiguous compression. Apply that compression and repeat until there are no uncompressed rules remaining. A valid prefix is one where the next character is a separator (in our case, either `/` or `_`) in the original string.

## Implementation

We show an example implementation in Python. The approach is to try every valid prefix starting with the shortest one until we find one that is unambiguous. Then, we find all rules matching that prefix and remove them from the set of uncompressed rules. One subtlety is that there may be no way to compress a given rule. In this case, we just add the rule as is to the output.

```python
def valid_prefixes(path):
    """Yields all valid prefixes for a given path."""
    for i, c in enumerate(path):
        if c in {"_", "/"}:
            yield path[:i]
    yield path


def is_unambiguous(rules, prefix, team):
    """Returns whether the given prefix and team is unambiguous."""
    return all(
        not rule_path.startswith(prefix) or rule_team == team
        for rule_path, rule_team in rules
    )


def rules_with_prefix(rules, prefix):
    """Returns a list of all rules with the given prefix."""
    return [rule for rule in rules if rule[0].startswith(prefix)]


def compress(rules):
    """Returns a list of unambiguous compressed rules for the given input."""
    compressed_rules = []
    rules_set = set(rules)

    while rules_set:
        path, team = next(iter(rules_set))

        for prefix in valid_prefixes(path):
            if is_unambiguous(rules, prefix, team):
                group = rules_with_prefix(rules, prefix)
                rules_set.difference_update(group)

                if len(group) == 1:
                    compressed_rules.extend(group)
                else:
                    compressed_rules.append((prefix + "*", team))

                break

    return sorted(compressed_rules)
```

Note that the time complexity of this implementation is not particularly great since we have to repeatedly test the entire set of rules against every possible prefix. However, this is more than fast enough for a CLI tool on the given input and achieves the desired output.

## Results

With this fairly simple algorithm, we were able to compress the ownership rules from around 120k characters to around 40k characters. This put us well below the 100k Sentry limit. The growth rate of the rules will also be slower since in most cases, an existing rule will cover new file paths and routes added under a shared prefix.

## Extensions

I thought of a two extensions to the existing solution that can improve the compression ratio and time complexity. Note that these do not necessarily result in readable rules or make the implementation easy to understand.

The first idea is that we can relax the constraint of only outputting unambiguous rules. For example, if a single team owned most of rules, then we could have the first rule be `*` and then add more granular rules after that (Sentry uses the last matched rule for routing). This can likely be done in a greedy manner where we look for the best team to compress at each step. However, we do have to ensure that each compressed rule does not match any previously compressed team's rules.

The second idea is that we can use a trie[^trie] (or radix tree[^radix]) data structure to improve lookup speed for a given prefix. During trie construction, we maintain a set (or a map counter) at each node that represents all teams which own any rule for the given prefix. When compressing, it takes constant time to check whether a given prefix is unambiguous. This approach is particularly useful if we needed to repeatedly compress the input while supporting rule insertions and deletions.

## References
[^sentry]: Sentry Documentation (2023). [Ownership Rules](https://docs.sentry.io/product/issues/ownership-rules/#limitations).
[^trie]: Wikipedia (2023). [Trie](https://en.wikipedia.org/wiki/Trie).
[^radix]: Wikipedia (2023). [Radix tree](https://en.wikipedia.org/wiki/Radix_tree).