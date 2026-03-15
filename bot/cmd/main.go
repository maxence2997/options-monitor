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
	port := os.Getenv("PORT")
	if port == "" {
		port = "8080"
	}

	// 驗證必要環境變數
	required := []string{"TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "GIST_ID", "GIST_TOKEN"}
	for _, key := range required {
		if os.Getenv(key) == "" {
			log.Fatalf("❌ 環境變數未設定：%s", key)
		}
	}

	gistStore := store.NewGistStore()
	cmdHandler := handlers.NewCommandHandler(gistStore)
	webhookHandler := handlers.NewWebhookHandler(cmdHandler)

	r := gin.Default()

	// Telegram Webhook endpoint
	// URL 帶入 bot token 作為安全驗證，避免非 Telegram 的請求
	webhookPath := fmt.Sprintf("/webhook/%s", os.Getenv("TELEGRAM_BOT_TOKEN"))
	r.POST(webhookPath, webhookHandler.HandleWebhook)

	// Health check（Railway 需要）
	r.GET("/health", webhookHandler.HealthCheck)
	r.GET("/", webhookHandler.HealthCheck)

	log.Printf("🚀 Bot server 啟動，port=%s", port)
	if err := r.Run(":" + port); err != nil {
		log.Fatalf("server error: %v", err)
	}
}
