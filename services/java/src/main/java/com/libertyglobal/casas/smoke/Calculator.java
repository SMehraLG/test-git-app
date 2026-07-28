package com.libertyglobal.casas.smoke;

/**
 * Trivial arithmetic used to exercise the factory's build → test-gate → PR flow
 * on a single-project Java (Maven) repo. Deliberately small and dependency-free.
 */
public final class Calculator {

    /** Returns the sum of {@code a} and {@code b}. */
    public int add(int a, int b) {
        return a + b;
    }

    /** Returns {@code a} minus {@code b}. */
    public int subtract(int a, int b) {
        return a - b;
    }

    /** Returns the product of {@code a} and {@code b}. */
    public int multiply(int a, int b) {
        return a * b;
    }
}
