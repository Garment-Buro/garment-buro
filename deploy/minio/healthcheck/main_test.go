package main

import (
	"net/http"
	"net/http/httptest"
	"sync/atomic"
	"testing"
	"time"
)

func TestOnlyReadyResponseIsHealthy(t *testing.T) {
	for _, status := range []int{200, 204, 301, 401, 503} {
		server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			w.WriteHeader(status)
		}))
		if got := healthy(server.Client(), server.URL); got != (status == 200) {
			t.Errorf("status %d: healthy=%t", status, got)
		}
		server.Close()
	}
}

func TestRedirectCannotMaskUnhealthyEndpoint(t *testing.T) {
	var followed atomic.Bool
	target := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		followed.Store(true)
	}))
	defer target.Close()
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		http.Redirect(w, r, target.URL, http.StatusFound)
	}))
	defer server.Close()
	client := server.Client()
	client.CheckRedirect = func(*http.Request, []*http.Request) error { return http.ErrUseLastResponse }
	if healthy(client, server.URL) || followed.Load() {
		t.Fatal("healthcheck followed a redirect")
	}
}

func TestSlowEndpointTimesOut(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		<-r.Context().Done()
	}))
	defer server.Close()
	client := server.Client()
	client.Timeout = 20 * time.Millisecond
	if healthy(client, server.URL) {
		t.Fatal("timed out endpoint reported healthy")
	}
}
