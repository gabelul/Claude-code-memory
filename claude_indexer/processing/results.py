"""Processing results for content processing operations."""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field


@dataclass
class ProcessingResult:
    """Result object for content processing operations."""
    
    success: bool
    error_message: Optional[str] = None
    items_processed: int = 0
    items_skipped: int = 0
    items_failed: int = 0
    cost_data: Dict[str, Any] = field(default_factory=dict)
    points_created: List[Any] = field(default_factory=list)
    
    @classmethod
    def success_result(cls, items_processed: int = 0, items_skipped: int = 0, 
                      cost_data: Dict[str, Any] = None, points_created: List[Any] = None) -> 'ProcessingResult':
        """Create a successful processing result."""
        return cls(
            success=True,
            items_processed=items_processed,
            items_skipped=items_skipped,
            cost_data=cost_data or {},
            points_created=points_created or []
        )
    
    @classmethod
    def failure_result(cls, error_message: str, items_failed: int = 0) -> 'ProcessingResult':
        """Create a failed processing result."""
        return cls(
            success=False,
            error_message=error_message,
            items_failed=items_failed
        )
    
    def combine_with(self, other: 'ProcessingResult') -> 'ProcessingResult':
        """Combine this result with another result."""
        if not self.success:
            return self
        if not other.success:
            return other
        
        # Combine cost data
        combined_cost = self.cost_data.copy()
        for key, value in other.cost_data.items():
            if key in combined_cost:
                combined_cost[key] += value
            else:
                combined_cost[key] = value
        
        return ProcessingResult(
            success=True,
            items_processed=self.items_processed + other.items_processed,
            items_skipped=self.items_skipped + other.items_skipped,
            items_failed=self.items_failed + other.items_failed,
            cost_data=combined_cost,
            points_created=self.points_created + other.points_created
        )