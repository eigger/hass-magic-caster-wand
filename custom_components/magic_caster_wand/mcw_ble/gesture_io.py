import json
import numpy as np
import os
from gesture_core import create_templates

class GestureIO:
    """
    Handles Input/Output for Gesture Data.
    Supports JSON, NPZ, and Direct Memory access.
    """

    @staticmethod
    def save(data: dict, path: str):
        """
        Save gesture data to a file. Format determined by extension (.json or .npz).
        Args:
            data: dict of {name: list_of_points (or numpy array)}
            path: file path
        """
        ext = os.path.splitext(path)[1].lower()
        
        # Convert all to list for JSON, ensure numpy for NPZ
        if ext == '.json':
            # Ensure lists
            serializable_data = {
                "type": "template_matcher",
                "templates": {k: np.array(v).tolist() for k, v in data.items()}
            }
            with open(path, 'w') as f:
                json.dump(serializable_data, f, indent=4)
            print(f"Saved to {path} (JSON)")
            
        elif ext == '.npz':
            # Ensure numpy
            np_data = {k: np.array(v, dtype=np.float32) for k, v in data.items()}
            np.savez_compressed(path, **np_data)
            print(f"Saved to {path} (NPZ)")
            
        else:
            raise ValueError(f"Unsupported format: {ext}")

    @staticmethod
    def load(source=None) -> dict:
        """
        Unified loader.
        Args:
            source: 
                - str: Path to .json or .npz file
                - None: Load directly from gesture_core (Memory)
        Returns:
            dict: {name: numpy_array(Nx2)}
        """
        templates = {}

        if source is None:
            print("Loading directly from Core (Memory)...")
            raw_data = create_templates()
            templates = {k: np.array(v, dtype=np.float32) for k, v in raw_data.items()}
            
        elif isinstance(source, str):
            if not os.path.exists(source):
                raise FileNotFoundError(f"File not found: {source}")
                
            ext = os.path.splitext(source)[1].lower()
            
            if ext == '.json':
                print(f"Loading from JSON: {source}")
                with open(source, 'r') as f:
                    data = json.load(f)
                # Structure check
                raw_templates = data.get("templates", data) 
                templates = {k: np.array(v, dtype=np.float32) for k, v in raw_templates.items()}
                
            elif ext == '.npz':
                print(f"Loading from NPZ: {source}")
                with np.load(source) as data:
                    templates = {k: data[k].astype(np.float32) for k in data.files}
                    
            else:
                raise ValueError(f"Unsupported format: {ext}")
                
        else:
            raise ValueError("Source must be a file path (str) or None (Memory)")
            
        return templates

if __name__ == "__main__":
    # Test IO
    # 1. Load from Core
    data = GestureIO.load(None) # from memory
    print(f"Loaded {len(data)} gestures from Memory.")
    
    # 2. Save to NPZ
    GestureIO.save(data, "test_model.npz")
    
    # 3. Load from NPZ
    data_npz = GestureIO.load("test_model.npz")
    print(f"Loaded {len(data_npz)} gestures from NPZ.")
    
    # 4. Save to JSON
    GestureIO.save(data, "test_model.json")
    
    # 5. Load from JSON
    data_json = GestureIO.load("test_model.json")
    print(f"Loaded {len(data_json)} gestures from JSON.")
