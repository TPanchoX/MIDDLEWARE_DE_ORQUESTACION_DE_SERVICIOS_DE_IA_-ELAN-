import math

import torch
from torch import nn


class KeypointTransformerClassifierV11(nn.Module):
    def __init__(
        self,
        input_dim: int,
        num_classes: int,
        d_model: int = 256,
        nhead: int = 8,
        num_layers: int = 4,
        dim_feedforward: int = 512,
        dropout: float = 0.2,
        max_len: int = 512,
    ) -> None:
        super().__init__()
        self.input_proj = nn.Sequential(
            nn.Linear(input_dim, d_model),
            nn.LayerNorm(d_model),
            nn.GELU(),
            nn.Dropout(dropout),
        )
        self.pos_encoder = PositionalEncoding(d_model=d_model, dropout=dropout, max_len=max_len)
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=d_model,
            nhead=nhead,
            dim_feedforward=dim_feedforward,
            dropout=dropout,
            batch_first=True,
            activation="gelu",
        )
        self.encoder = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)
        self.pool = AttentionPooling(d_model=d_model)
        self.classifier = nn.Sequential(
            nn.Linear(d_model, 128),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(128, num_classes),
        )

    def forward(self, x: torch.Tensor, mask: torch.Tensor | None = None) -> dict[str, torch.Tensor]:
        if x.ndim != 3:
            raise ValueError("KeypointTransformerClassifierV11 expects input shape [B, T, D].")

        valid_mask = mask.bool() if mask is not None else torch.ones(x.shape[:2], dtype=torch.bool, device=x.device)
        padding_mask = ~valid_mask
        encoded = self.input_proj(x)
        encoded = self.pos_encoder(encoded)
        encoded = self.encoder(encoded, src_key_padding_mask=padding_mask)
        pooled = self.pool(encoded, valid_mask)
        logits = self.classifier(pooled)
        return {"logits": logits}


class PositionalEncoding(nn.Module):
    def __init__(self, d_model: int, dropout: float, max_len: int) -> None:
        super().__init__()
        self.dropout = nn.Dropout(dropout)

        position = torch.arange(max_len, dtype=torch.float32).unsqueeze(1)
        div_term = torch.exp(torch.arange(0, d_model, 2, dtype=torch.float32) * (-math.log(10000.0) / d_model))
        encoding = torch.zeros(max_len, d_model, dtype=torch.float32)
        encoding[:, 0::2] = torch.sin(position * div_term)
        encoding[:, 1::2] = torch.cos(position * div_term)
        self.register_buffer("pe", encoding.unsqueeze(0))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.dropout(x + self.pe[:, : x.shape[1], :])


class AttentionPooling(nn.Module):
    def __init__(self, d_model: int) -> None:
        super().__init__()
        self.attn = nn.Linear(d_model, 1)

    def forward(self, values: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
        scores = self.attn(values).squeeze(-1)
        scores = scores.masked_fill(~mask, torch.finfo(scores.dtype).min)
        weights = torch.softmax(scores, dim=1).unsqueeze(-1)
        weights = torch.where(mask.unsqueeze(-1), weights, torch.zeros_like(weights))
        normalizer = weights.sum(dim=1, keepdim=True).clamp_min(torch.finfo(weights.dtype).eps)
        weights = weights / normalizer
        return (values * weights).sum(dim=1)
