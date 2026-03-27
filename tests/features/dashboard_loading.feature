Feature: Dashboard Data Loading
  As a dashboard user
  I want the data loader to provide accurate snapshots
  So that I see up-to-date market information

  Scenario: Data loader returns historical panel and latest snapshot
    Given the daily_metrics parquet file exists
    When the data loader reads the file
    Then it should return two DataFrames
    And the latest DataFrame should have one row per ISIN
    And the historical DataFrame should have more rows than the latest

  Scenario: All required columns are present
    Given the daily_metrics parquet file exists
    When the data loader reads the file
    Then both DataFrames should contain column Isin
    And both DataFrames should contain column Datum
    And both DataFrames should contain column anomaly_score
    And both DataFrames should contain column volume_today_chf
