package com.libertyglobal.casas.smoke;

import static org.junit.jupiter.api.Assertions.assertEquals;

import org.junit.jupiter.api.Test;

class CalculatorTest {

    private final Calculator calculator = new Calculator();

    @Test
    void addsTwoPositiveNumbers() {
        assertEquals(5, calculator.add(2, 3));
    }

    @Test
    void addsNegativeNumbers() {
        assertEquals(-5, calculator.add(-2, -3));
    }

    @Test
    void subtractsTwoNumbers() {
        assertEquals(-1, calculator.subtract(2, 3));
    }

    @Test
    void multipliesTwoPositives() {
        assertEquals(6, calculator.multiply(2, 3));
    }

    @Test
    void multipliesWithZeroOperand() {
        assertEquals(0, calculator.multiply(5, 0));
    }

    @Test
    void multipliesWithNegative() {
        assertEquals(-6, calculator.multiply(-2, 3));
    }

    @Test
    void multipliesTwoNegatives() {
        assertEquals(6, calculator.multiply(-2, -3));
    }
}
