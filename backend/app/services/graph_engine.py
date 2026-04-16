import networkx as nx
import math
from typing import List, Dict, Optional, Tuple
from app.models.schemas import FloorPlanData, Node, Edge

class GraphEngine:
    def __init__(self, data: FloorPlanData):
        self.data = data
        self.graph = nx.Graph()
        self._build_graph()

    def _build_graph(self):
        for node in self.data.nodes:
            self.graph.add_node(
                node.id, 
                label=node.label, 
                node_type=node.node_type, 
                coords=(node.x, node.y),
                confidence=node.confidence
            )
        
        for edge in self.data.edges:
            self.graph.add_edge(
                edge.source, 
                edge.target, 
                weight=edge.distance, 
                is_door=edge.is_door
            )

    def heuristic(self, node_a: str, node_b: str) -> float:
        coords_a = self.graph.nodes[node_a].get("coords")
        coords_b = self.graph.nodes[node_b].get("coords")
        
        if not coords_a or not coords_b:
            return 0.0
            
        return math.sqrt((coords_a[0] - coords_b[0])**2 + (coords_a[1] - coords_b[1])**2)

    def find_shortest_path(self, source_id: str, target_id: str) -> Optional[List[str]]:
        try:
            path = nx.astar_path(
                self.graph, 
                source=source_id, 
                target=target_id, 
                heuristic=self.heuristic, 
                weight='weight'
            )
            return path
        except nx.NetworkXNoPath:
            return None
        except nx.NodeNotFound:
            return None

    def get_path_details(self, path: List[str]) -> List[Dict]:
        details = []
        for i in range(len(path)):
            node_id = path[i]
            node_data = self.graph.nodes[node_id]
            step = {
                "id": node_id,
                "label": node_data.get("label"),
                "type": node_data.get("node_type"),
                "confidence": node_data.get("confidence")
            }
            if i < len(path) - 1:
                next_node = path[i+1]
                edge_data = self.graph.get_edge_data(node_id, next_node)
                step["distance_to_next"] = edge_data.get("weight")
                step["passes_door"] = edge_data.get("is_door")
            details.append(step)
            
        return details
        
    def export_adjacency_list(self) -> Dict[str, List[Dict]]:
        adjacency = {}
        for node in self.graph.nodes:
            neighbors = []
            for neighbor in self.graph.neighbors(node):
                edge_data = self.graph.get_edge_data(node, neighbor)
                neighbor_data = self.graph.nodes[neighbor]
                neighbors.append({
                    "id": neighbor,
                    "label": neighbor_data.get("label"),
                    "distance": round(edge_data.get("weight", 0), 2)
                })
            adjacency[node] = neighbors
        return adjacency
