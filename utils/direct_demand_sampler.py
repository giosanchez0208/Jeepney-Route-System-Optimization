import os
import json
import math
import random
import hashlib
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
    idw_power: float = 2.0
    cache_dir: str = "utils/.cache"
    
    # Cochran's Formula Parameters
    z_score: float = 1.96        # 95% Confidence Level
    proportion: float = 0.5      # Maximum Variance
    margin_error: float = 0.05   # 5% Margin of Error
    api_limit_override: Optional[int] = None

class TrafficClient:
    """
    Standalone client for network requests and caching.
    Decouples TomTom API logic from the mathematical sampling engine.
    """
    def __init__(self, api_key: Optional[str], cache_dir: str, verbose: bool = False):
        if not api_key:
            raise ValueError("[ENVIRONMENT] TOMTOM_API_KEY is missing from the .env file.")
        self.api_key = api_key
        self.cache_dir = cache_dir
        self.verbose = verbose
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
        only_drivable: bool = False,
        verbose: bool = False
    ):
        self.city = city
        self.config = config
        self.verbose = verbose
        
        self.target_nodes = self._filter_nodes(only_drivable)
        self.node_list = list(self.target_nodes)
        self.n = len(self.node_list)
        
        if self.n == 0:
            raise ValueError("[DIRECT DEMAND] No valid nodes available for sampling.")

        self.api_sample_limit = self._calculate_optimal_sample_size()

        if self.verbose:
            print(f"[STATISTICS] Population Size (N): {self.n}")
            print(f"[STATISTICS] Computed Sample Size (n): {self.api_sample_limit}")

        self.prob = [0.0] * self.n
        self.alias = [0] * self.n
        self.node_probabilities = {}
        self.max_prob = 0.0
        
        self.traffic_client = TrafficClient(TOMTOM_API_KEY, self.config.cache_dir, self.verbose)
        
        centrality_scores = self._compute_centrality()
        target_centroids = self._select_query_centroids()
        empirical_traffic = self.traffic_client.gather_empirical_traffic(target_centroids)
        traffic_weights = self._impute_traffic(empirical_traffic)
        
        ddm_probabilities = self._apply_ddm(traffic_weights, centrality_scores)
        self._build_alias_tables(ddm_probabilities)

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
            print(f"[DIRECT DEMAND] Selecting {self.api_sample_limit} evenly spaced target nodes for API queries.")
            
        sorted_nodes = sorted(self.node_list, key=lambda n: (n.lon, n.lat))
        step = max(1, self.n // self.api_sample_limit)
        return sorted_nodes[::step][:self.api_sample_limit]

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

        for node in iterable:
            if node in empirical:
                imputed[node] = empirical[node]
                continue
                
            numerator = 0.0
            denominator = 0.0
            
            for k_node in known_nodes:
                dist = math.hypot(node.lon - k_node.lon, node.lat - k_node.lat)
                if dist == 0:
                    dist = 0.0001
                
                weight = 1.0 / (dist ** self.config.idw_power)
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

    def get_point(self) -> Node:
        i = random.randint(0, self.n - 1)
        if random.random() <= self.prob[i]:
            return self.node_list[i]
        return self.node_list[self.alias[i]]

    def draw_density(self, img_map: Image.Image, context: tuple[tuple[float, float], tuple[float, float]], num_points: int = 5000) -> None:
        print("\n[bold]Traffic Density Spectrum Legend:[/bold]")
        print("[blue]██[/blue] Low Traffic")
        print("[yellow]██[/yellow] Moderate Traffic")
        print("[red]██[/red] High Traffic")
        
        draw = ImageDraw.Draw(img_map)
        tl_lon, tl_lat = context[0]
        br_lon, br_lat = context[1]
        lon_range = br_lon - tl_lon
        lat_range = tl_lat - br_lat

        for _ in range(num_points):
            node = self.get_point()
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