package main

import (
	"fmt"
	"log"
	"os"

	"github.com/gin-gonic/gin"

	"options-monitor/bot/handlers"
	"options-monitor/bot/store"
)

func main() {
	log.SetOutput(os.Stdout)
	port := os.Getenv("PORT")
	if port == "" {
		port = "8080"
	}

	// 必填環境變數
	required := []string{"TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "GIST_ID", "GIST_TOKEN"}
	for _, key := range required {
		if os.Getenv(key) == "" {
			log.Fatalf("❌ 環境變數未設定：%s", key)
		}
	}

	// /trigger 指令需要這兩個，選填（未設定時 /trigger 會提示錯誤）
	if os.Getenv("GITHUB_TOKEN") == "" {
		log.Println("⚠️  GITHUB_TOKEN 未設定，/trigger 指令將無法使用")
	}
	if os.Getenv("GITHUB_REPO") == "" {
		log.Println("⚠️  GITHUB_REPO 未設定，/trigger 指令將無法使用")
	}

	gistStore     := store.NewGistStore()
	cmdHandler    := handlers.NewCommandHandler(gistStore)
	webhookHandler := handlers.NewWebhookHandler(cmdHandler)

	r := gin.Default()

	webhookPath := fmt.Sprintf("/webhook/%s", os.Getenv("TELEGRAM_BOT_TOKEN"))
	r.POST(webhookPath, webhookHandler.HandleWebhook)
	r.GET("/health", webhookHandler.HealthCheck)
	r.GET("/", webhookHandler.HealthCheck)

	log.Printf("🚀 Bot server 啟動，port=%s", port)
	if err := r.Run(":" + port); err != nil {
		log.Fatalf("server error: %v", err)
	}
}
