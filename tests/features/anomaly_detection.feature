Feature: Anomaly Detection
  As a market analyst
  I want the system to detect anomalous trading activity
  So that I can investigate suspicious patterns

  Scenario: Volume spike is detected
    Given a security with 30 days of normal volume around 50 units
    When a trading day has volume exceeding 1.5 times the 30-day median
    Then the volume_spike flag should be True
    And the anomaly_score should be at least 3

  Scenario: No anomaly for uniform trading
    Given a security with 30 days of identical trades at price 100 and volume 50
    When the metrics pipeline processes the data
    Then all anomaly_score values should be 0

  Scenario: Price gap is detected
    Given a security with 30 days of stable prices at 100
    When a trading day has a price change exceeding 5 percent
    Then the price_gap flag should be True
    And the anomaly_score should be at least 2

  Scenario: Combined spike yields maximum score
    Given a security with 30 days of normal trading
    When a day has volume spike and activity spike and price gap
    Then the anomaly_score should be 7
