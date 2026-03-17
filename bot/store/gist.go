package store

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"time"

	"options-monitor/bot/model"
)

const gistFilename = "positions.json"

type GistStore struct {
	gistID string
	token  string
	client *http.Client
}

func NewGistStore() *GistStore {
	return &GistStore{
		gistID: os.Getenv("GIST_ID"),
		token:  os.Getenv("GIST_TOKEN"),
		client: &http.Client{Timeout: 10 * time.Second},
	}
}

// Load 從 Gist 讀取整個 Store
func (g *GistStore) Load() (*model.Store, error) {
	url := fmt.Sprintf("https://api.github.com/gists/%s", g.gistID)
	req, _ := http.NewRequest("GET", url, nil)
	req.Header.Set("Authorization", "Bearer "+g.token)
	req.Header.Set("Accept", "application/vnd.github+json")

	resp, err := g.client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("gist fetch error: %w", err)
	}
	defer resp.Body.Close()

	var gistResp struct {
		Files map[string]struct {
			Content string `json:"content"`
		} `json:"files"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&gistResp); err != nil {
		return nil, fmt.Errorf("gist decode error: %w", err)
	}

	file, ok := gistResp.Files[gistFilename]
	if !ok || file.Content == "" {
		return &model.Store{NextID: 1, Positions: []model.Position{}}, nil
	}

	var store model.Store
	if err := json.Unmarshal([]byte(file.Content), &store); err != nil {
		return nil, fmt.Errorf("store unmarshal error: %w", err)
	}
	return &store, nil
}

// Save 將 Store 寫回 Gist
func (g *GistStore) Save(store *model.Store) error {
	store.LastUpdate = time.Now()

	content, err := json.MarshalIndent(store, "", "  ")
	if err != nil {
		return fmt.Errorf("marshal error: %w", err)
	}

	body := map[string]interface{}{
		"files": map[string]interface{}{
			gistFilename: map[string]string{
				"content": string(content),
			},
		},
	}
	bodyBytes, _ := json.Marshal(body)

	url := fmt.Sprintf("https://api.github.com/gists/%s", g.gistID)
	req, _ := http.NewRequest("PATCH", url, bytes.NewReader(bodyBytes))
	req.Header.Set("Authorization", "Bearer "+g.token)
	req.Header.Set("Accept", "application/vnd.github+json")
	req.Header.Set("Content-Type", "application/json")

	resp, err := g.client.Do(req)
	if err != nil {
		return fmt.Errorf("gist save error: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		b, _ := io.ReadAll(resp.Body)
		return fmt.Errorf("gist save failed (%d): %s", resp.StatusCode, string(b))
	}
	return nil
}

// AddPosition 新增持倉並儲存
func (g *GistStore) AddPosition(req *model.AddPositionRequest) (*model.Position, error) {
	store, err := g.Load()
	if err != nil {
		return nil, err
	}

	pos := model.Position{
		ID:              store.NextID,
		Strategy:        req.Strategy,
		Symbol:          req.Symbol,
		Status:          model.StatusOpen,
		OpenDate:        time.Now().Format("2006-01-02"),
		Expiry:          req.Expiry,
		Contracts:       req.Contracts,
		Notes:           req.Notes,
		CreatedAt:       time.Now(),
		ProfitTargetPct: req.DefaultProfitTarget(),
		LossLimitPct:    req.DefaultLossLimit(),

		// 非 IC 策略欄位
		StrikeSell:      req.StrikeSell,
		StrikeBuy:       req.StrikeBuy,
		PremiumReceived: req.PremiumReceived,

		// IC 專用欄位（非 IC 策略這六個會是 0，因 omitempty 不寫入 JSON）
		PutStrikeShort:  req.PutStrikeShort,
		PutStrikeLong:   req.PutStrikeLong,
		PutPremium:      req.PutPremium,
		CallStrikeShort: req.CallStrikeShort,
		CallStrikeLong:  req.CallStrikeLong,
		CallPremium:     req.CallPremium,
	}

	store.Positions = append(store.Positions, pos)
	store.NextID++

	if err := g.Save(store); err != nil {
		return nil, err
	}
	return &pos, nil
}

// UpdateStatus 更新持倉狀態
func (g *GistStore) UpdateStatus(id int, status model.Status, note string) (*model.Position, error) {
	store, err := g.Load()
	if err != nil {
		return nil, err
	}

	for i, p := range store.Positions {
		if p.ID == id {
			store.Positions[i].Status = status
			if note != "" {
				if store.Positions[i].Notes != "" {
					store.Positions[i].Notes += " | " + note
				} else {
					store.Positions[i].Notes = note
				}
			}
			if err := g.Save(store); err != nil {
				return nil, err
			}
			updated := store.Positions[i]
			return &updated, nil
		}
	}
	return nil, fmt.Errorf("持倉 ID=%d 不存在", id)
}

// ListOpen 回傳所有 OPEN 持倉
func (g *GistStore) ListOpen() ([]model.Position, error) {
	store, err := g.Load()
	if err != nil {
		return nil, err
	}
	var open []model.Position
	for _, p := range store.Positions {
		if p.Status == model.StatusOpen {
			open = append(open, p)
		}
	}
	return open, nil
}
