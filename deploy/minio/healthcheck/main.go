package main

import (
	"net/http"
	"os"
	"time"
)

func healthy(client *http.Client, endpoint string) bool {
	response, err := client.Get(endpoint)
	if err != nil {
		return false
	}
	defer response.Body.Close()
	return response.StatusCode == http.StatusOK
}

func main() {
	client := &http.Client{
		Timeout: 3 * time.Second,
		CheckRedirect: func(*http.Request, []*http.Request) error {
			return http.ErrUseLastResponse
		},
	}
	if !healthy(client, "http://127.0.0.1:9000/minio/health/live") {
		os.Exit(1)
	}
}
