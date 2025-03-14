---
title: Add input validation and type checking for a Custom Expectation 
---

import Prerequisites from '../creating_custom_expectations/components/prerequisites.jsx'
import TechnicalTag from '@site/docs/reference/learn/term_tags/_tag.mdx';

## Prerequisites

<Prerequisites>

 - [Created a Custom Expectation](../custom_expectations_lp.md)

</Prerequisites>

<p class="markdown"><TechnicalTag tag="expectation" text="Expectations" /> will typically be configured using input parameters. These parameters are required to provide your <TechnicalTag tag="custom_expectation" text="Custom Expectation" /> with the context it needs to <TechnicalTag tag="validation" text="Validate" /> your data.  Ensuring that these requirements are fulfilled is the purpose of type checking and validating your input parameters.</p>

For example, we might expect the fraction of null values to be `mostly=.05`, in which case any value above 1 would indicate an impossible fraction of a single whole (since a value above one indicates more than a single whole), and should throw an error. Another example would be if we want to indicate that the mean of a row adheres to a minimum value bound, such as `min_value=5`. In this case, attempting to pass in a non numerical value should clearly throw an error!

This guide will walk you through the process of adding validation and Type Checking to the input parameters of the Custom Expectation built in the guide for [how to create a Custom Column Aggregate Expectation](../creating_custom_expectations/how_to_create_custom_column_aggregate_expectations.md). When you have completed this guide, you will have implemented a method to validate that the input parameters provided to this Custom Expectation satisfy the requirements necessary for them to be used as intended by the Custom Expectation's code.

## Decide what to validate

As a general rule, we want to validate any of our input parameters and success keys that are explicitly used by our Expectation class.
In the case of our example Expectation `expect_column_max_to_be_between_custom`, we've defined four parameters to validate:

- `min_value`: An integer or float defining the lowest acceptable bound for our column max
- `max_value`: An integer or float defining the highest acceptable bound for our column max
- `strict_min`: A boolean value defining whether our column max *is* (`strict_min=False`) or *is not* (`strict_min=True`) allowed to equal the `min_value`
- `strict_max`: A boolean value defining whether our column max *is* (`strict_max=False`) or *is not* (`strict_max=True`) allowed to equal the `max_value`

<details>
    <summary>What don't we need to validate?</summary>
You may have noticed we're not validating whether the <inlineCode>column</inlineCode> parameter has been set.
Great Expectations implicitly handles the validation of certain parameters universal to each class of Expectation, so you don't have to!
</details>

## Define the Validation method

We define the `validate_configuration(...)` method of our Custom Expectation class to ensure that the input parameters constitute a valid configuration, 
and doesn't contain illogical or incorrect values. For example, if `min_value` is greater than `max_value`, `max_value=True`, or `strict_min=Joe`, we want to throw an exception.
To do this, we're going to write a series of `assert` statements to catch invalid values for our parameters.

To begin with, we want to create our `validate_configuration(...)` method and ensure that a configuration is set:

```python name="tests/integration/docusaurus/expectations/creating_custom_expectations/expect_column_max_to_be_between_custom.py validate_config"
```

Next, we're going to implement the logic for validating the four parameters we identified above.

## Access parameters and writing assertions

First we need to access the parameters to be evaluated:

```python name="tests/integration/docusaurus/expectations/creating_custom_expectations/expect_column_max_to_be_between_custom.py validate_config_params"
```

Now we can begin writing the assertions to validate these parameters. 

We're going to ensure that at least one of `min_value` or `max_value` is set:

```python name="tests/integration/docusaurus/expectations/creating_custom_expectations/expect_column_max_to_be_between_custom.py validate_config_values"
```

Check that `min_value` and `max_value` are of the correct type:

```python name="tests/integration/docusaurus/expectations/creating_custom_expectations/expect_column_max_to_be_between_custom.py validate_config_types"
```

Verify that, if both `min_value` and `max_value` are set, `min_value` does not exceed `max_value`:

```python name="tests/integration/docusaurus/expectations/creating_custom_expectations/expect_column_max_to_be_between_custom.py validate_config_comparison"
```

And assert that `strict_min` and `strict_max`, if provided, are of the correct type:

```python name="tests/integration/docusaurus/expectations/creating_custom_expectations/expect_column_max_to_be_between_custom.py validate_config_none"
```

If any of these fail, we raise an exception:

```python name="tests/integration/docusaurus/expectations/creating_custom_expectations/expect_column_max_to_be_between_custom.py validate_config_except"
```

Putting this all together, our `validate_configuration(...)` method should verify that all necessary inputs have been provided, 
that all inputs are of the correct types, that they have a correct relationship between each other, and that if any of these conditions aren't met, 
we raise an exception.

## Verify your method

If you now run your file, `print_diagnostic_checklist()` will attempt to execute the `validate_configuration(...)` using the input provided in your [Example Cases](./how_to_add_example_cases_for_an_expectation.md).

If your input is successfully validated, and the rest the logic in your Custom Expectation is already complete, you will see the following in your Diagnostic Checklist:

```console
 ✔ Has basic input validation and type checking
    ✔ Custom 'assert' statements in validate_configuration
```

<div style={{"text-align":"center"}}>
<p style={{"color":"#8784FF","font-size":"1.4em"}}><b>
Congratulations!<br/>&#127881; You've successfully added input validation & type checking to a Custom Expectation! &#127881;
</b></p>
</div>

## Contribution (Optional)

The method implemented in this guide is an optional feature for Experimental Expectations, and a requirement for [contribution](https://github.com/great-expectations/great_expectations/blob/develop/CONTRIBUTING_EXPECTATIONS.md) to Great Expectations at Beta and Production levels.

If you would like to contribute your Custom Expectation to the Great Expectations codebase, please submit a [Pull Request](https://github.com/great-expectations/great_expectations/pulls).

:::note
For more information on our code standards and contribution, see our guide on [Levels of Maturity](/docs/oss/contributing/contributing_maturity#expectation-contributions) for Expectations.

To view the full script used in this page, see it on GitHub:
- [expect_column_max_to_be_between_custom.py](https://github.com/great-expectations/great_expectations/blob/develop/tests/integration/docusaurus/expectations/creating_custom_expectations/expect_column_max_to_be_between_custom.py)
:::