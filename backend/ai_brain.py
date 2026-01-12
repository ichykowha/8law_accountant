import torch
import torch.nn as nn

class AccountingBrain(nn.Module):
    def __init__(self, input_size=128, hidden_size=256, output_size=10):
        super(AccountingBrain, self).__init__()
        # Layer 1: Data Ingestion (Takes raw numbers in)
        self.input_layer = nn.Linear(input_size, hidden_size)
        
        # Layer 2: Deep Analysis (The "Thinking" Layer)
        self.hidden_layer = nn.Linear(hidden_size, hidden_size)
        
        # Layer 3: Decision/Classification Output (The final tax category)
        self.output_layer = nn.Linear(hidden_size, output_size)
        
        # Activation for non-linear logic (Allows it to understand complex patterns)
        self.relu = nn.ReLU()

    def forward(self, x):
        # Pass data through input layer -> Activate
        x = self.relu(self.input_layer(x))
        # Pass through hidden analysis layer -> Activate
        x = self.relu(self.hidden_layer(x))
        # Final decision
        x = self.output_layer(x)
        return x

# Helper function to get the brain ready for the app
def get_brain():
    brain = AccountingBrain()
    # We will load saved memories (weights) here later
    return brain

if __name__ == "__main__":
    # Test to make sure it starts up
    brain = get_brain()
    print("Base Neural Network Module Initialized.")
    print(brain)