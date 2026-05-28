# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Online Boutique — Google's cloud-first microservices demo e-commerce app. 11+ microservices in Go, C#, Node.js, Python, and Java, all communicating over gRPC.

## Build & Deploy Commands

### Deploy with pre-built images (recommended for quick start)
```sh
kubectl apply -f release/kubernetes-manifests.yaml
```
Note: `kubernetes-manifests/` uses short image names (for skaffold local builds). `release/kubernetes-manifests.yaml` has full Google Artifact Registry paths.

### Local development with Skaffold
```sh
skaffold run          # build + deploy (first run ~20 min)
skaffold dev          # watch mode, auto-rebuild on code changes
skaffold delete       # cleanup
```

### Access the app
```sh
kubectl port-forward svc/frontend 8080:80
# Visit http://localhost:8080
```

### Run frontend tests
```sh
cd src/frontend && go test ./...
```

## Architecture

All services communicate via gRPC. Protocol buffer definitions are in `protos/demo.proto`.

**Request flow:** User → frontend (Go, HTTP) → checkoutservice (Go, gRPC) → [cartservice, paymentservice, shippingservice, emailservice, currencyservice]

| Service | Language | Key detail |
|---------|----------|------------|
| frontend | Go | HTTP server, serves HTML templates from `src/frontend/templates/` |
| checkoutservice | Go | Orchestrates cart, payment, shipping, email |
| cartservice | C# | Stores cart in Redis, **needs ≥256Mi memory** (64Mi default causes OOM) |
| productcatalogservice | Go | Reads products from JSON |
| currencyservice | Node.js | ECB exchange rates, highest QPS |
| paymentservice | Node.js | Mock credit card charging |
| shippingservice | Go | Mock shipping estimates |
| emailservice | Python | Mock order confirmation emails |
| recommendationservice | Python | Product recommendations |
| adservice | Java | Context-based text ads |
| loadgenerator | Python/Locust | Simulates user traffic |

## Key Technical Details

- **Frontend templates** are parsed at Go startup via `ParseGlob("templates/*.html")`. CSS/static files are served from filesystem. Changing templates requires a pod restart; CSS changes just need a browser refresh.
- **cartservice** ships with a 64Mi memory limit in the manifests but needs ~256Mi. Patch after deploy: `kubectl patch deployment cartservice -p '{"spec":{"template":{"spec":{"containers":[{"name":"server","resources":{"limits":{"memory":"256Mi"}}}]}}}}'`
- **frontend-external** is LoadBalancer type — in kind/minikube clusters it stays Pending. Use `kubectl port-forward` instead.
- Environment variables control service discovery (e.g. `CART_SERVICE_ADDR`, `PRODUCT_CATALOG_SERVICE_ADDR`). See `kubernetes-manifests/frontend.yaml` for the full list.
- `CYMBAL_BRANDING=true` switches to "Cymbal Shops" branding variant.

## Service Directory Layout

Each service lives in `src/<service-name>/` with its own Dockerfile and language-specific build. The Go services share nothing — each is a standalone module with its own `go.mod`.
