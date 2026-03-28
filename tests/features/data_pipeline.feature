Feature: Data Pipeline Metrics
  As a data engineer
  I want the pipeline to produce correct daily metrics
  So that downstream dashboards display accurate information

  Scenario: Pipeline produces one row per ISIN per trading day
    Given raw trade data with 3 ISINs and 5 trading days each
    When the metrics pipeline processes the trades
    Then the output should have 15 rows
    And each row should have a positive trade count

  Scenario: Price bounds are consistent
    Given raw trade data with multiple intraday prices
    When the metrics pipeline processes the intraday data
    Then price_min should be less than or equal to price_max for every row
    And price_first and price_last should be within the min-max range
