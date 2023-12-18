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


print(
    compress(
        [
            ("*/routes/asset/asset_report_create.go", "#team-assets"),
            ("*/routes/asset/asset_report_get.go", "#team-assets"),
            ("*/routes/asset/asset_report_pdf_get.go", "#team-assets"),
            ("*/routes/investments/investment_holdings_get.go", "#team-investments"),
            (
                "*/routes/investments/investment_transactions_get.go",
                "#team-investments",
            ),
            ("*/routes/investments/test.go", "#team-platform"),
        ]
    )
)
