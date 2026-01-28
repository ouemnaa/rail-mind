"""
Graph Neural Network for rail network embeddings.
Encodes the rail network graph structure into dense embeddings.
"""
import numpy as np
from typing import List, Optional, Callable
from dataclasses import dataclass

from .data_structures import RailGraph, Context


@dataclass 
class GNNConfig:
    """Configuration for GNN model."""
    input_dim: int = 16
    hidden_dim: int = 64
    output_dim: int = 128
    num_layers: int = 3
    aggregation: str = "mean"  # "mean", "sum", "max"
    dropout: float = 0.1


class MessagePassingLayer:
    """
    Single message passing layer.
    
    For each node i:
        m_i = AGGREGATE({h_j : j in N(i)})
        h_i' = UPDATE(h_i, m_i)
    """
    
    def __init__(
        self,
        input_dim: int,
        output_dim: int,
        aggregation: str = "mean"
    ):
        self.input_dim = input_dim
        self.output_dim = output_dim
        self.aggregation = aggregation
        
        # Learnable weights (initialized randomly)
        self.W_msg = np.random.randn(input_dim, output_dim) * 0.1
        self.W_update = np.random.randn(input_dim + output_dim, output_dim) * 0.1
        self.bias = np.zeros(output_dim)
    
    def forward(
        self,
        node_features: np.ndarray,
        edge_index: np.ndarray,
        edge_features: Optional[np.ndarray] = None
    ) -> np.ndarray:
        """
        Forward pass of message passing.
        
        Args:
            node_features: (num_nodes, input_dim)
            edge_index: (2, num_edges) - [source, target]
            edge_features: (num_edges, edge_dim) optional
        
        Returns:
            updated_features: (num_nodes, output_dim)
        """
        num_nodes = node_features.shape[0]
        source, target = edge_index[0], edge_index[1]
        
        # Compute messages from source nodes
        messages = node_features[source] @ self.W_msg
        
        # Optionally incorporate edge features
        if edge_features is not None:
            # Simple: add edge features to messages
            if edge_features.shape[1] == messages.shape[1]:
                messages = messages + edge_features
        
        # Aggregate messages at each target node
        aggregated = np.zeros((num_nodes, self.output_dim))
        counts = np.zeros(num_nodes)
        
        for i, (msg, tgt) in enumerate(zip(messages, target)):
            aggregated[tgt] += msg
            counts[tgt] += 1
        
        # Apply aggregation type
        if self.aggregation == "mean":
            counts = np.maximum(counts, 1)  # avoid division by zero
            aggregated = aggregated / counts[:, np.newaxis]
        elif self.aggregation == "max":
            # For max, we'd need a different approach - simplified here
            pass
        # "sum" is already computed
        
        # Update: combine with original features
        combined = np.concatenate([node_features, aggregated], axis=1)
        updated = combined @ self.W_update + self.bias
        
        # Activation (ReLU)
        updated = np.maximum(0, updated)
        
        return updated


class GraphEncoder:
    """
    Multi-layer GNN encoder.
    Stacks multiple message passing layers.
    """
    
    def __init__(self, config: GNNConfig):
        self.config = config
        self.layers: List[MessagePassingLayer] = []
        
        # Build layers
        dims = [config.input_dim] + [config.hidden_dim] * (config.num_layers - 1) + [config.output_dim]
        
        for i in range(config.num_layers):
            layer = MessagePassingLayer(
                input_dim=dims[i],
                output_dim=dims[i + 1],
                aggregation=config.aggregation
            )
            self.layers.append(layer)
    
    def encode(
        self,
        graph: RailGraph,
        return_node_embeddings: bool = False
    ) -> np.ndarray:
        """
        Encode graph into embedding.
        
        Args:
            graph: RailGraph with node features and edge index
            return_node_embeddings: if True, return per-node embeddings
        
        Returns:
            graph_embedding: (output_dim,) or (num_nodes, output_dim) if return_node_embeddings
        """
        h = graph.node_features
        
        # Apply each message passing layer
        for layer in self.layers:
            h = layer.forward(h, graph.edge_index, graph.edge_features)
            
            # Apply dropout (simplified - just scaling)
            if self.config.dropout > 0:
                mask = np.random.binomial(1, 1 - self.config.dropout, h.shape)
                h = h * mask / (1 - self.config.dropout)
        
        if return_node_embeddings:
            return h
        
        # Global pooling: mean of all node embeddings
        graph_embedding = np.mean(h, axis=0)
        return graph_embedding


class GNNEmbedder:
    """
    Complete GNN-based embedder for rail network.
    Combines graph structure with operational context.
    """
    
    def __init__(self, config: Optional[GNNConfig] = None):
        self.config = config or GNNConfig()
        self.encoder = GraphEncoder(self.config)
        
        # Context projection
        context_dim = 5  # from Context.to_vector()
        self.context_proj = np.random.randn(context_dim, 32) * 0.1
        
        # Final fusion layer
        fusion_input = self.config.output_dim + 32
        self.fusion_layer = np.random.randn(fusion_input, self.config.output_dim) * 0.1
    
    def embed(
        self,
        graph: RailGraph,
        context: Optional[Context] = None
    ) -> np.ndarray:
        """
        Generate embedding for rail network state.
        
        Args:
            graph: Rail network graph
            context: Operational context (optional)
        
        Returns:
            embedding: (output_dim,) dense embedding
        """
        # Encode graph
        graph_emb = self.encoder.encode(graph)
        
        if context is None:
            return graph_emb
        
        # Encode context
        context_vec = context.to_vector()
        context_emb = np.maximum(0, context_vec @ self.context_proj)
        
        # Fuse graph and context
        combined = np.concatenate([graph_emb, context_emb])
        fused = np.tanh(combined @ self.fusion_layer)
        
        return fused
    
    def embed_conflict(
        self,
        graph: RailGraph,
        conflict_node_ids: List[str],
        context: Optional[Context] = None
    ) -> np.ndarray:
        """
        Generate embedding focused on conflict area.
        
        Args:
            graph: Full rail network graph
            conflict_node_ids: IDs of nodes involved in conflict
            context: Operational context
        
        Returns:
            conflict_embedding: (output_dim,) embedding focused on conflict
        """
        # Get node embeddings
        node_embs = self.encoder.encode(graph, return_node_embeddings=True)
        
        # Extract embeddings for conflict nodes
        if graph.node_ids:
            conflict_indices = [
                graph.node_ids.index(nid) 
                for nid in conflict_node_ids 
                if nid in graph.node_ids
            ]
        else:
            # Assume sequential indexing
            conflict_indices = list(range(min(len(conflict_node_ids), len(node_embs))))
        
        if not conflict_indices:
            return np.mean(node_embs, axis=0)
        
        # Pool conflict node embeddings
        conflict_embs = node_embs[conflict_indices]
        conflict_pooled = np.mean(conflict_embs, axis=0)
        
        # Combine with context if provided
        if context is not None:
            context_vec = context.to_vector()
            context_emb = np.maximum(0, context_vec @ self.context_proj)
            combined = np.concatenate([conflict_pooled, context_emb])
            return np.tanh(combined @ self.fusion_layer)
        
        return conflict_pooled


# Utility functions for building rail graphs

def build_rail_graph(
    stations: List[dict],
    connections: List[dict],
    delays: dict
) -> RailGraph:
    """
    Build RailGraph from station and connection data.
    
    Args:
        stations: List of {"id": str, "capacity": int, "type": str, ...}
        connections: List of {"from": str, "to": str, "distance": float, ...}
        delays: Dict of station_id -> current_delay
    
    Returns:
        RailGraph ready for GNN encoding
    """
    node_ids = [s["id"] for s in stations]
    node_id_to_idx = {nid: i for i, nid in enumerate(node_ids)}
    
    # Node features: [capacity, type_encoding, delay, ...]
    node_features = []
    for station in stations:
        type_map = {"terminal": 0, "junction": 1, "through": 2}
        features = [
            station.get("capacity", 1) / 10.0,
            type_map.get(station.get("type", "through"), 2) / 2.0,
            delays.get(station["id"], 0) / 60.0,  # normalize delay to hours
            1.0  # bias term
        ]
        # Pad to input_dim
        while len(features) < 16:
            features.append(0.0)
        node_features.append(features[:16])
    
    node_features = np.array(node_features)
    
    # Edge index: bidirectional connections
    sources, targets = [], []
    edge_features_list = []
    
    for conn in connections:
        # Support both "from"/"to" and "source"/"target" formats
        src_key = "source" if "source" in conn else "from"
        tgt_key = "target" if "target" in conn else "to"
        
        src_idx = node_id_to_idx.get(conn.get(src_key))
        tgt_idx = node_id_to_idx.get(conn.get(tgt_key))
        
        if src_idx is not None and tgt_idx is not None:
            # Forward edge
            sources.append(src_idx)
            targets.append(tgt_idx)
            # Support both "distance" and "distance_km" formats
            dist = conn.get("distance_km", conn.get("distance", 1))
            edge_features_list.append([dist / 100.0])
            
            # Backward edge (bidirectional)
            sources.append(tgt_idx)
            targets.append(src_idx)
            edge_features_list.append([dist / 100.0])
    
    edge_index = np.array([sources, targets])
    edge_features = np.array(edge_features_list) if edge_features_list else None
    
    return RailGraph(
        node_features=node_features,
        edge_index=edge_index,
        edge_features=edge_features,
        node_ids=node_ids
    )
