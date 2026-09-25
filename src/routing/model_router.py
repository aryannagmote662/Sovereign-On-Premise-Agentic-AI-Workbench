"""
Intelligent Model Router Implementation for MRPL AI Workbench.
Routes user queries to target local model managers based on intent classification.
Never communicates directly with Ollama APIs.
"""

import logging
import time
from typing import Any, Dict, Optional

from config.settings import settings
from typing import TYPE_CHECKING, Any, Dict, Optional

if TYPE_CHECKING:
    from src.models.base_model import BaseModel

from src.routing.base_router import BaseRouter, RoutingResult
from src.routing.intent_classifier import IntentClassifier, UserIntent
from src.routing.routing_rules import RoutingRules

logger = logging.getLogger("MRPL.ModelRouter")


class ModelRouter(BaseRouter):
    """
    Intelligent Model Router automating model selection for MRPL workbench tasks.
    Coordinates IntentClassifier and RoutingRules while logging telemetry metrics.
    """

    def __init__(
        self,
        classifier: Optional[IntentClassifier] = None,
        rules: Optional[RoutingRules] = None,
    ) -> None:
        self.classifier = classifier or IntentClassifier()
        self.rules = rules or RoutingRules()

    def route(
        self,
        request: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> RoutingResult:
        """
        Route request to local model manager based on intent classification and rules.

        Args:
            request: User input prompt string.
            context: Optional contextual parameters.

        Returns:
            RoutingResult object containing selected manager and routing telemetry.
        """
        start_time = time.perf_counter()
        ctx = context or {}

        try:
            # 1. Intent Classification
            classification = self.classifier.classify(request=request, context=ctx)
            intent = classification.intent
            confidence = classification.confidence if settings.ENABLE_CONFIDENCE else 1.0
            matched_rule = classification.matched_rule

            # 2. Map Intent to Model Manager
            manager: BaseModel = self.rules.get_manager(intent)
            selected_model = manager.model_name

            # Determine routing status
            status = "FALLBACK" if intent == UserIntent.UNKNOWN else "SUCCESS"

            # 3. Calculate Routing Execution Time
            elapsed_time_ms = (time.perf_counter() - start_time) * 1000.0

            result = RoutingResult(
                manager=manager,
                selected_model=selected_model,
                intent=intent.value,
                confidence=confidence,
                routing_time_ms=elapsed_time_ms,
                status=status,
                user_query=request,
                reasoning=matched_rule,
                metadata={
                    **classification.metadata,
                    "router_type": settings.ROUTER_TYPE,
                },
            )

            # 4. Structured Telemetry Logging
            if settings.ENABLE_ROUTING_LOGS:
                self._log_routing_telemetry(result)

            try:
                from src.observability.telemetry_service import get_telemetry_service
                telemetry = get_telemetry_service()
                telemetry.update_workflow_stage(
                    stage="ROUTING",
                    status="COMPLETED",
                    query=request,
                    route=intent.value,
                    model=selected_model,
                )
                telemetry.update_workflow_stage(
                    stage="AUTHORIZATION",
                    status="ACTIVE",
                )
            except Exception:
                pass

            return result

        except Exception as exc:
            elapsed_time_ms = (time.perf_counter() - start_time) * 1000.0
            fallback_manager = self.rules.get_manager(UserIntent.UNKNOWN)
            err_result = RoutingResult(
                manager=fallback_manager,
                selected_model=fallback_manager.model_name,
                intent=UserIntent.UNKNOWN.value,
                confidence=0.0,
                routing_time_ms=elapsed_time_ms,
                status="ERROR",
                user_query=request,
                reasoning=f"Exception encountered: {str(exc)}",
                metadata={"error": str(exc)},
            )
            if settings.ENABLE_ROUTING_LOGS:
                logger.error(
                    f"[ROUTING ERROR] query='{request}' | error='{str(exc)}' | fallback_model='{fallback_manager.model_name}'"
                )
            return err_result

    def _log_routing_telemetry(self, result: RoutingResult) -> None:
        """
        Emit structured log entry containing user query, intent, selected model, routing time, status.
        """
        query_snippet = (
            result.user_query[:50] + "..." if len(result.user_query) > 50 else result.user_query
        )
        logger.info(
            f"[MODEL ROUTER] status={result.status} | "
            f"user_query='{query_snippet}' | "
            f"detected_intent={result.intent} | "
            f"selected_model='{result.selected_model}' | "
            f"routing_time={result.routing_time_ms:.2f}ms | "
            f"confidence={result.confidence:.2f}"
        )
