"""
Calibration Benchmark - Measure Confidence Accuracy

If the system says 90% confidence, is it actually right 90% of the time?

This is critical for autonomous systems.
"""

from typing import List, Dict, Any, Tuple
import numpy as np


class CalibrationBenchmark:
    """
    Test whether confidence predictions match actual accuracy.
    
    Perfect calibration: predicted confidence = actual accuracy
    """
    
    def __init__(self):
        self.predictions: List[Tuple[float, bool]] = []
    
    def record_prediction(self, confidence: float, correct: bool):
        """Record a prediction with confidence and whether it was correct"""
        self.predictions.append((confidence, correct))
    
    def compute_calibration(self) -> Dict[str, Any]:
        """
        Compute calibration metrics.
        
        Returns:
        - calibration_error: Expected Calibration Error (ECE)
        - brier_score: Brier score
        - calibration_curve: Confidence bins vs actual accuracy
        """
        if not self.predictions:
            return {"error": "No predictions recorded"}
        
        # Group by confidence bins
        bins = self._create_bins()
        
        # Expected Calibration Error
        ece = self._compute_ece(bins)
        
        # Brier Score
        brier = self._compute_brier_score()
        
        # Calibration curve
        curve = self._compute_calibration_curve(bins)
        
        return {
            "expected_calibration_error": ece,
            "brier_score": brier,
            "calibration_curve": curve,
            "total_predictions": len(self.predictions),
            "overall_accuracy": sum(1 for _, correct in self.predictions if correct) / len(self.predictions)
        }
    
    def _create_bins(self, num_bins: int = 10) -> Dict[int, List[Tuple[float, bool]]]:
        """Group predictions into confidence bins"""
        bins = {i: [] for i in range(num_bins)}
        
        for confidence, correct in self.predictions:
            bin_idx = min(int(confidence * num_bins), num_bins - 1)
            bins[bin_idx].append((confidence, correct))
        
        return bins
    
    def _compute_ece(self, bins: Dict) -> float:
        """
        Expected Calibration Error
        
        Average difference between confidence and accuracy across bins
        """
        ece = 0.0
        total = len(self.predictions)
        
        for bin_predictions in bins.values():
            if not bin_predictions:
                continue
            
            # Average confidence in bin
            avg_confidence = sum(conf for conf, _ in bin_predictions) / len(bin_predictions)
            
            # Actual accuracy in bin
            accuracy = sum(1 for _, correct in bin_predictions if correct) / len(bin_predictions)
            
            # Weighted difference
            weight = len(bin_predictions) / total
            ece += weight * abs(avg_confidence - accuracy)
        
        return ece
    
    def _compute_brier_score(self) -> float:
        """
        Brier Score
        
        Mean squared error of probability predictions
        Lower is better (0 = perfect)
        """
        return sum((conf - (1.0 if correct else 0.0)) ** 2 for conf, correct in self.predictions) / len(self.predictions)
    
    def _compute_calibration_curve(self, bins: Dict) -> List[Dict[str, float]]:
        """
        Calibration curve data
        
        For each bin: predicted confidence vs actual accuracy
        """
        curve = []
        
        for bin_idx, bin_predictions in bins.items():
            if not bin_predictions:
                continue
            
            avg_confidence = sum(conf for conf, _ in bin_predictions) / len(bin_predictions)
            accuracy = sum(1 for _, correct in bin_predictions if correct) / len(bin_predictions)
            
            curve.append({
                "bin": bin_idx,
                "predicted_confidence": avg_confidence,
                "actual_accuracy": accuracy,
                "gap": abs(avg_confidence - accuracy),
                "count": len(bin_predictions)
            })
        
        return curve
    
    def is_well_calibrated(self, threshold: float = 0.1) -> bool:
        """
        Check if system is well calibrated.
        
        threshold: Maximum acceptable ECE
        """
        metrics = self.compute_calibration()
        return metrics.get("expected_calibration_error", 1.0) < threshold


def test_calibration():
    """Example usage"""
    benchmark = CalibrationBenchmark()
    
    # Simulate predictions
    # Perfect calibration
    for _ in range(90):
        benchmark.record_prediction(0.9, True)
    for _ in range(10):
        benchmark.record_prediction(0.9, False)
    
    # Poor calibration (overconfident)
    for _ in range(50):
        benchmark.record_prediction(0.95, True)
    for _ in range(50):
        benchmark.record_prediction(0.95, False)
    
    results = benchmark.compute_calibration()
    print(f"ECE: {results['expected_calibration_error']:.3f}")
    print(f"Brier: {results['brier_score']:.3f}")
    print(f"Well calibrated: {benchmark.is_well_calibrated()}")


if __name__ == "__main__":
    test_calibration()
