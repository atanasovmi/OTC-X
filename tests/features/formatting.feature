Feature: Formatting Utilities
  As a frontend developer
  I want formatting functions to handle all value ranges
  So that the dashboard displays clean, consistent data

  Scenario Outline: CHF formatting handles various magnitudes
    Given a numeric value <value>
    When formatted as CHF
    Then the result should contain "<expected_part>"

    Examples:
      | value    | expected_part |
      | 1500000  | CHF 1.50M     |
      | 42.50    | CHF 42.50     |
      | 0        | CHF 0.00      |

  Scenario: NaN values display as dash
    Given a NaN value
    When formatted as CHF
    Then the result should be the dash character

  Scenario: Percentage formatting includes sign
    Given a positive percentage value 3.14
    When formatted as percentage
    Then the result should start with a plus sign

  Scenario: Negative percentage formatting
    Given a negative percentage value -2.50
    When formatted as percentage
    Then the result should start with a minus sign
