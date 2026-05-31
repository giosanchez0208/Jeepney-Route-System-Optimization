import os
import json
import math
import random
import hashlib
import pickle
import requests
import networkx as nx
from typing import Optional, Protocol, Any
from dataclasses import dataclass
from tqdm import tqdm
from dotenv import load_dotenv
from rich import print
from PIL import ImageDraw, Image

from .node import Node

load_dotenv()
TOMTOM_API_KEY = os.getenv("TOMTOM_API_KEY")

class NetworkGraph(Protocol):
    """
    Dependency inversion protocol. 
    Defines required attributes for any spatial graph passed to the sampler.
    """
    nodes: set[Node]
    graph: list[Any]
    _road_graph: nx.MultiDiGraph
    _node_lookup: dict[int, Node]

@dataclass
class DDMConfig:
    """
    Standardized configuration for the Direct Demand Model equations.
    """
    alpha: float = 0.6
    beta: float = 0.4
    cache_dir: str = "utils/.cache"
    
    # Cochran's Formula Parameters
    z_score: float = 1.96        # 95% Confidence Level
    proportion: float = 0.5      # Maximum Variance
    margin_error: float = 0.05   # 5% Margin of Error
    api_limit_override: Optional[int] = None

DDM_MODEL_CACHE_VERSION = 2

def _node_cache_key(node: Node) -> tuple[float, float, Optional[int]]:
    return (round(node.lon, 10), round(node.lat, 10), getattr(node, "layer", None))

def _city_cache_signature(city: NetworkGraph) -> str:
    graph_cache_path = getattr(city, "_graph_cache_path", "")
    if graph_cache_path:
        base = graph_cache_path
    else:
        node_bits = "|".join(
            f"{round(node.lon, 10)}:{round(node.lat, 10)}:{getattr(node, 'layer', None)}"
            for node in sorted(city.nodes, key=_node_cache_key)
        )
        base = f"{len(city.nodes)}|{len(city.graph)}|{node_bits}"
    return hashlib.md5(base.encode()).hexdigest()

def _config_signature(config: DDMConfig) -> str:
    payload = {
        "alpha": config.alpha,
        "beta": config.beta,
        "z_score": config.z_score,
        "proportion": config.proportion,
        "margin_error": config.margin_error,
        "api_limit_override": config.api_limit_override,
        "cache_dir": config.cache_dir,
    }
    return hashlib.md5(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

class TrafficClient:
    """
    Standalone client for network requests and caching.
    Decouples TomTom API logic from the mathematical sampling engine.
    """
    def __init__(self, api_key: Optional[str], cache_dir: str, verbose: bool = False):
        if not api_key:
            raise ValueError("[ENVIRONMENT] TOMTOM_API_KEY is missing from the .env file.")
        self.api_key = api_key
        self.verbose = verbose
        
        # Isolate TomTom API payloads
        self.cache_dir = os.path.join(cache_dir, "tomtom_api")
        os.makedirs(self.cache_dir, exist_ok=True)

    def gather_empirical_traffic(self, target_nodes: list[Node]) -> dict[Node, float]:
        empirical_data = {}
        iterable = target_nodes
        if self.verbose:
            iterable = tqdm(iterable, desc="Querying TomTom Flow API")
            
        for node in iterable:
            weight = self._query_api(node)
            if weight is not None:
                empirical_data[node] = weight
                
        return empirical_data

    def _query_api(self, node: Node) -> Optional[float]:
        cache_key = hashlib.md5(f"{node.lat}_{node.lon}".encode()).hexdigest()
        cache_path = os.path.join(self.cache_dir, f"tomtom_{cache_key}.json")
        
        if os.path.exists(cache_path):
            with open(cache_path, "r") as f:
                data = json.load(f)
                return data.get("weight")

        url = f"https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json?point={node.lat},{node.lon}&key={self.api_key}"
        
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                flow = data.get("flowSegmentData", {})
                current_speed = flow.get("currentSpeed", 1)
                free_flow = flow.get("freeFlowSpeed", 1)
                
                weight = free_flow / max(current_speed, 1)
                
                with open(cache_path, "w") as f:
                    json.dump({"weight": weight, "raw": flow}, f)
                    
                return weight
            else:
                return None
        except requests.exceptions.RequestException:
            return None

class DirectDemandSampler:
    """
    Direct Demand Model Spatial Sampler.
    
    Academic Justifications & Equations:
    1. Direct Demand Model (DDM): P_i = (W_i^alpha * C_i^beta) / sum(...)
    2. Inverse Distance Weighting (IDW): W_j = sum(V_i / d_{ij}^p) / sum(...)
    3. Walker's Alias Method for O(1) Sampling.
    """

    def __init__(
        self, 
        city: NetworkGraph, 
        config: DDMConfig = DDMConfig(),
        verbose: bool = False
    ):
        self.city = city
        self.config = config
        self.verbose = verbose
        
        self.drivable_nodes = self._extract_drivable_nodes()
        self.target_nodes = self.city.nodes
        self.node_list = sorted(self.target_nodes, key=_node_cache_key)
        self.n = len(self.node_list)
        
        if self.n == 0:
            raise ValueError("[DIRECT DEMAND] No valid nodes available for sampling.")

        self._node_lookup = {_node_cache_key(node): node for node in self.node_list}
        self._cache_dir = os.path.join(self.config.cache_dir, "ddm_models")
        os.makedirs(self._cache_dir, exist_ok=True)
        self._cache_path = os.path.join(self._cache_dir, f"{self._build_cache_key()}.pkl")

        self.api_sample_limit = 0
        self.prob = [0.0] * self.n
        self.alias = [0] * self.n
        self.node_probabilities = {}
        self.max_prob = 0.0
        self.centrality_scores: dict[Node, float] = {}
        self.target_centroids: list[Node] = []
        self.empirical_traffic: dict[Node, float] = {}
        self.traffic_weights: dict[Node, float] = {}
        self.raw_probabilities: list[float] = []
        self.traffic_client: Optional[TrafficClient] = None

        if self._load_cache():
            if self.verbose:
                print(f"[DIRECT DEMAND] Loaded sampler cache from {self._cache_path}.")
            return

        self.api_sample_limit = self._calculate_optimal_sample_size()

        if self.verbose:
            print(f"[STATISTICS] Population Size (N): {self.n}")
            print(f"[STATISTICS] Computed Sample Size (n): {self.api_sample_limit}")

        self.traffic_client = TrafficClient(TOMTOM_API_KEY, self.config.cache_dir, self.verbose)
        
        self.centrality_scores = self._compute_centrality()
        self.target_centroids = self._select_query_centroids()
        self.empirical_traffic = self.traffic_client.gather_empirical_traffic(self.target_centroids)
        self.traffic_weights = self._impute_traffic(self.empirical_traffic)
        
        self.raw_probabilities = self._apply_ddm(self.traffic_weights, self.centrality_scores)
        self._build_alias_tables(self.raw_probabilities)
        self._save_cache()

    
    def _calculate_optimal_sample_size(self) -> int:
        if self.config.api_limit_override is not None:
            return self.config.api_limit_override

        N = self.n
        Z = self.config.z_score
        p = self.config.proportion
        e = self.config.margin_error
        q = 1.0 - p
        
        n_0 = ((Z ** 2) * p * q) / (e ** 2)
        optimal_size = math.ceil(n_0 / (1 + ((n_0 - 1) / N)))
        return optimal_size

    def _extract_drivable_nodes(self) -> set[Node]:
        drivable_nodes = set()
        for edge in getattr(self.city, "graph", []):
            if getattr(edge, "is_drivable", False):
                drivable_nodes.add(edge.start)
                drivable_nodes.add(edge.end)
        return drivable_nodes

    def _build_cache_key(self) -> str:
        signature = {
            "city": _city_cache_signature(self.city),
            "config": _config_signature(self.config),
            "nodes": self.n,
        }
        return hashlib.md5(json.dumps(signature, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    def _resolve_node(self, key: tuple[float, float, Optional[int]]) -> Node:
        node = self._node_lookup.get(key)
        if node is None:
            raise ValueError("[DIRECT DEMAND] Cached sampler refers to nodes not present in the current CityGraph.")
        return node

    def _load_cache(self) -> bool:
        if not os.path.exists(self._cache_path):
            return False

        with open(self._cache_path, "rb") as f:
            payload = pickle.load(f)

        if not isinstance(payload, dict):
            return False

        if payload.get("version") != DDM_MODEL_CACHE_VERSION:
            return False

        if payload.get("cache_key") != self._build_cache_key():
            return False

        self.api_sample_limit = payload["api_sample_limit"]
        self.prob = list(payload["prob"])
        self.alias = list(payload["alias"])
        
        # Rebuild dictionaries using the deterministic index of self.node_list
        self.node_probabilities = {self.node_list[idx]: v for idx, v in payload["node_probabilities"].items()}
        self.max_prob = payload["max_prob"]
        
        self.centrality_scores = {self.node_list[idx]: v for idx, v in payload.get("centrality_scores", {}).items()}
        self.target_centroids = [self.node_list[idx] for idx in payload.get("target_centroids", [])]
        self.empirical_traffic = {self.node_list[idx]: v for idx, v in payload.get("empirical_traffic", {}).items()}
        self.traffic_weights = {self.node_list[idx]: v for idx, v in payload.get("traffic_weights", {}).items()}
        
        self.raw_probabilities = list(payload.get("raw_probabilities", []))
        return True

    def _save_cache(self) -> None:
        # Create a reverse lookup to map Node instances to their stable integer index
        node_to_idx = {node: i for i, node in enumerate(self.node_list)}
        
        payload = {
            "version": DDM_MODEL_CACHE_VERSION,
            "cache_key": self._build_cache_key(),
            "api_sample_limit": self.api_sample_limit,
            "prob": self.prob,
            "alias": self.alias,
            "node_probabilities": {node_to_idx[n]: v for n, v in self.node_probabilities.items()},
            "max_prob": self.max_prob,
            "centrality_scores": {node_to_idx[n]: v for n, v in self.centrality_scores.items()},
            "target_centroids": [node_to_idx[n] for n in self.target_centroids],
            "empirical_traffic": {node_to_idx[n]: v for n, v in self.empirical_traffic.items()},
            "traffic_weights": {node_to_idx[n]: v for n, v in self.traffic_weights.items()},
            "raw_probabilities": self.raw_probabilities,
        }

        with open(self._cache_path, "wb") as f:
            pickle.dump(payload, f)

    def _filter_nodes(self, only_drivable: bool) -> set[Node]:
        if not only_drivable:
            return self.city.nodes

        drivable_nodes = set()
        for edge in self.city.graph:
            if edge.is_drivable:
                drivable_nodes.add(edge.start)
                drivable_nodes.add(edge.end)
        return drivable_nodes

    def _compute_centrality(self) -> dict[Node, float]:
        if self.verbose:
            print("[DIRECT DEMAND] Computing betweenness centrality approximation.")
        
        subgraph = self.city._road_graph.subgraph(
            [osm_id for osm_id, node in self.city._node_lookup.items() if node in self.target_nodes]
        )
        
        k_samples = min(100, len(subgraph.nodes))
        raw_centrality = nx.betweenness_centrality(subgraph, k=k_samples, weight="length", normalized=True)
        
        centrality_map = {}
        for osm_id, score in raw_centrality.items():
            node = self.city._node_lookup.get(osm_id)
            if node in self.target_nodes:
                centrality_map[node] = score + 0.0001

        return centrality_map

    def _select_query_centroids(self) -> list[Node]:
        if self.api_sample_limit >= self.n:
            if self.verbose:
                print(f"[DIRECT DEMAND] API limit covers population. Querying all {self.n} target nodes.")
            return self.node_list
            
        if self.verbose:
            print(f"[DIRECT DEMAND] Selecting {self.api_sample_limit} target nodes using centrality-weighted sampling.")
            
        # Xie & Levinson (2007) Alignment: 
        # Shift from uniform random sampling to Centrality-Weighted Sampling.
        # This uses the Efraimidis and Spirakis (2006) method for weighted 
        # random sampling without replacement.
        
        weighted_nodes = sorted(
            self.centrality_scores.keys(),
            key=lambda node: math.log(random.random()) / self.centrality_scores[node],
            reverse=True
        )
        
        return weighted_nodes[:self.api_sample_limit]

    def _impute_traffic(self, empirical: dict[Node, float]) -> dict[Node, float]:
        if self.verbose:
            print("[DIRECT DEMAND] Executing IDW traffic imputation.")
            
        known_nodes = list(empirical.keys())
        if not known_nodes:
            if self.verbose:
                print("[WARNING] No empirical data retrieved. Defaulting to baseline weights.")
            return {node: 1.0 for node in self.target_nodes}

        imputed = {}
        iterable = self.target_nodes
        if self.verbose:
            iterable = tqdm(iterable, desc="Imputing unknown nodes")

        def haversine(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
            lon1, lat1, lon2, lat2 = map(math.radians, [lon1, lat1, lon2, lat2])
            dlon = lon2 - lon1
            dlat = lat2 - lat1
            a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
            return 6371000 * (2 * math.asin(math.sqrt(a)))

        for node in iterable:
            if node in empirical:
                imputed[node] = empirical[node]
                continue
                
            numerator = 0.0
            denominator = 0.0
            
            for k_node in known_nodes:
                dist = haversine(node.lon, node.lat, k_node.lon, k_node.lat)
                if dist == 0:
                    dist = 0.0001
                
                weight = 1.0 / (dist ** 2.0)
                numerator += empirical[k_node] * weight
                denominator += weight
                
            imputed[node] = numerator / denominator

        return imputed

    def _apply_ddm(self, traffic: dict[Node, float], centrality: dict[Node, float]) -> list[float]:
        raw_probs = []
        for node in self.node_list:
            w_i = traffic.get(node, 1.0)
            c_i = centrality.get(node, 0.0001)
            p_i = (w_i ** self.config.alpha) * (c_i ** self.config.beta)
            raw_probs.append(p_i)
            
        return raw_probs

    def _build_alias_tables(self, raw_probs: list[float]) -> None:
        total_prob = sum(raw_probs)
        if total_prob == 0:
            raise ValueError("[DIRECT DEMAND] Total DDM probability evaluates to zero.")

        for i, node in enumerate(self.node_list):
            self.node_probabilities[node] = raw_probs[i] / total_prob
        self.max_prob = max(self.node_probabilities.values())

        scaled_probs = [(p / total_prob) * self.n for p in raw_probs]
        
        small = []
        large = []
        
        for i, p in enumerate(scaled_probs):
            if p < 1.0:
                small.append(i)
            else:
                large.append(i)

        while small and large:
            l = small.pop()
            g = large.pop()
            
            self.prob[l] = scaled_probs[l]
            self.alias[l] = g
            
            scaled_probs[g] = (scaled_probs[g] + scaled_probs[l]) - 1.0
            
            if scaled_probs[g] < 1.0:
                small.append(g)
            else:
                large.append(g)

        while large:
            self.prob[large.pop()] = 1.0
            
        while small:
            self.prob[small.pop()] = 1.0

    def get_point(self, only_drivable: bool = False) -> Node:
        if only_drivable and not self.drivable_nodes:
            raise ValueError("[DIRECT DEMAND] Cannot sample drivable nodes. City graph contains 0 drivable edges.")

        while True:
            i = random.randint(0, self.n - 1)
            if random.random() <= self.prob[i]:
                node = self.node_list[i]
            else:
                node = self.node_list[self.alias[i]]
                
            if not only_drivable or node in self.drivable_nodes:
                return node

    def draw_density(self, img_map: Image.Image, context: tuple[tuple[float, float], tuple[float, float]], num_points: int = 5000, only_drivable: bool = False) -> None:
        draw = ImageDraw.Draw(img_map)
        tl_lon, tl_lat = context[0]
        br_lon, br_lat = context[1]
        lon_range = br_lon - tl_lon
        lat_range = tl_lat - br_lat

        for _ in range(num_points):
            node = self.get_point(only_drivable=only_drivable)
            prob_ratio = self.node_probabilities[node] / self.max_prob
            
            if prob_ratio < 0.5:
                t = prob_ratio * 2.0
                r = int(255 * t)
                g = int(255 * t)
                b = int(255 * (1 - t))
            else:
                t = (prob_ratio - 0.5) * 2.0
                r = 255
                g = int(255 * (1 - t))
                b = 0
                
            color = (r, g, b, 128)

            x = (node.lon - tl_lon) / lon_range * img_map.width
            y = (tl_lat - node.lat) / lat_range * img_map.height
            
            draw.ellipse((x-2, y-2, x+2, y+2), fill=color)