import torch
from torch import nn


class VideoBinarySegmenter(nn.Module):
    def __init__(
        self,
        input_channels: int = 3,
        cnn_feature_dim: int = 32,
        lstm_hidden_size: int = 64,
        lstm_layers: int = 1,
    ) -> None:
        super().__init__()
        self.frame_encoder = nn.Sequential(
            nn.Conv2d(input_channels, 16, kernel_size=3, padding=1),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(kernel_size=2),
            nn.Conv2d(16, cnn_feature_dim, kernel_size=3, padding=1),
            nn.ReLU(inplace=True),
            nn.AdaptiveAvgPool2d((1, 1)),
        )
        self.temporal_encoder = nn.LSTM(
            input_size=cnn_feature_dim,
            hidden_size=lstm_hidden_size,
            num_layers=lstm_layers,
            batch_first=True,
            bidirectional=True,
        )
        self.classifier = nn.Linear(lstm_hidden_size * 2, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        if x.ndim != 5:
            raise ValueError("VideoBinarySegmenter expects input shape [B, T, C, H, W].")

        batch_size, time_steps, channels, height, width = x.shape
        frame_batch = x.reshape(batch_size * time_steps, channels, height, width)
        frame_features = self.frame_encoder(frame_batch)
        frame_features = frame_features.flatten(start_dim=1)
        temporal_features = frame_features.reshape(batch_size, time_steps, -1)
        encoded_sequence, _ = self.temporal_encoder(temporal_features)
        logits = self.classifier(encoded_sequence)
        return logits.squeeze(-1)
