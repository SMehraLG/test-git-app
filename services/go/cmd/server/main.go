package main

import (
	"encoding/json"
	"log"
	"net/http"
	"os"

	calculator "github.com/Liberty-Global-Tech/casas-infra-platform-demo/services/go"
)

func main() {
	port := os.Getenv("PORT")
	if port == "" {
		port = "8080"
	}

	mux := http.NewServeMux()

	mux.HandleFunc("GET /healthz", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]string{"status": "ok"})
	})

	mux.HandleFunc("GET /", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]any{
			"service": "smoke-go",
			"ops":     []string{"add", "subtract"},
			"sample":  calculator.Add(2, 3),
		})
	})

	log.Printf("smoke-go listening on :%s", port)
	log.Fatal(http.ListenAndServe(":"+port, mux))
}
