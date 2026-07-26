# Model Runtime Router

Choose an available local or cloud model class for one prompt role.

Consider modality, context size, reasoning need, privacy, credential state, latency, cost, determinism, and fallback. Never include credentials in the route. Prefer local execution when data policy requires it. Return only JSON matching `nmsr.model-route/1`.
