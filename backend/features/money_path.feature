# HUMAN-OWNED. This file is the specification of the money path. Agents must not edit it.
Feature: Paid run lifecycle
  As the operator of a paid service
  I want payment events processed exactly once
  So that no customer is double-charged and no run executes unpaid or twice

  Scenario: A payment webhook funds a pending run exactly once
    Given a pending run awaiting payment
    When the payment event is confirmed
    Then the run is paid

  Scenario: A replayed payment webhook is a no-op
    Given a pending run awaiting payment
    When the payment event is confirmed
    And the same payment event is delivered again
    Then the run is paid
    And the second delivery is recognized as a duplicate

  Scenario: An unpaid run cannot be claimed for execution
    Given a pending run awaiting payment
    When a worker tries to claim the run for execution
    Then the claim is refused

  Scenario: Concurrent workers cannot both execute a paid run
    Given a paid run
    When two workers race to claim the run
    Then exactly one claim succeeds
