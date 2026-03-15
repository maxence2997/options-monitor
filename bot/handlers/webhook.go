package handlers

import (
	"bytes"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"

	"github.com/gin-gonic/gin"
)

type WebhookHandler struct {
	cmd      *CommandHandler
	botToken string
	chatID   string
}

func NewWebhookHandler(cmd *CommandHandler) *WebhookHandler {
	return &WebhookHandler{
		cmd:      cmd,
		botToken: os.Getenv("TELEGRAM_BOT_TOKEN"),
		chatID:   os.Getenv("TELEGRAM_CHAT_ID"),
	}
}

// TelegramUpdate represents an incoming Telegram update
type TelegramUpdate struct {
	UpdateID int `json:"update_id"`
	Message  struct {
		MessageID int `json:"message_id"`
		From      struct {
			ID int64 `json:"id"`
		} `json:"from"`
		Chat struct {
			ID int64 `json:"id"`
		} `json:"chat"`
		Text string `json:"text"`
	} `json:"message"`
}

// HandleWebhook processes incoming Telegram webhook requests
func (h *WebhookHandler) HandleWebhook(c *gin.Context) {
	var update TelegramUpdate
	if err := c.ShouldBindJSON(&update); err != nil {
		log.Printf("webhook bind error: %v", err)
		c.Status(http.StatusBadRequest)
		return
	}

	text := update.Message.Text
	chatID := update.Message.Chat.ID

	if text == "" {
		c.Status(http.StatusOK)
		return
	}

	log.Printf("[msg] chat=%d text=%q", chatID, text)

	response := h.cmd.Dispatch(text)
	if err := h.sendMessage(chatID, response); err != nil {
		log.Printf("send message error: %v", err)
	}

	c.Status(http.StatusOK)
}

// HealthCheck handles health check endpoint
func (h *WebhookHandler) HealthCheck(c *gin.Context) {
	c.JSON(http.StatusOK, gin.H{"status": "ok"})
}

func (h *WebhookHandler) sendMessage(chatID int64, text string) error {
	url := fmt.Sprintf("https://api.telegram.org/bot%s/sendMessage", h.botToken)

	body := map[string]interface{}{
		"chat_id":    chatID,
		"text":       text,
		"parse_mode": "HTML",
	}
	bodyBytes, _ := json.Marshal(body)

	resp, err := http.Post(url, "application/json", bytes.NewReader(bodyBytes))
	if err != nil {
		return fmt.Errorf("telegram send error: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("telegram send failed: %d", resp.StatusCode)
	}
	return nil
}
