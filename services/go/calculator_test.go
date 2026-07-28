package calculator

import "testing"

func TestAdd(t *testing.T) {
	if got := Add(2, 3); got != 5 {
		t.Errorf("Add(2, 3) = %d; want 5", got)
	}
}

func TestAddNegative(t *testing.T) {
	if got := Add(-2, -3); got != -5 {
		t.Errorf("Add(-2, -3) = %d; want -5", got)
	}
}

func TestSubtract(t *testing.T) {
	if got := Subtract(5, 2); got != 3 {
		t.Errorf("Subtract(5, 2) = %d; want 3", got)
	}
}
