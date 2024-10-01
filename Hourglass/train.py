import torch
import time
import tqdm
from torch.utils.data import Dataset, DataLoader
from model import HourglassLM

###############################################################
# Training file of the Hourglass model for language modeling
###############################################################

# Factors for the hourglass blocks, each factor is a list of two integers [n_layers, factor].
# The first k factor is always 1 no matter what, otherwise the length of the output doesn't match the input.
factors = [[2, 1], [1, 3]] # Total number of layers in the model is 2 + 1 + 2 = 5 (like an hourglass).
batch_size = 64
block_size = 256
epochs = 2
learning_rate = 3e-4
n_heads=6
n_embedding=384

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

###############################################################

with open('lovecraft-stories.txt', 'r', encoding='utf-8') as f:
    text = f.read()

chars = sorted(list(set(text)))
vocab_size = len(chars)

char_to_idx = {ch: i for i, ch in enumerate(chars)} # character to index mapping
idx_to_char = {i: ch for i, ch in enumerate(chars)} # index to character mapping

def encoder(text):
    return [char_to_idx[ch] for ch in text]

def decoder(text):
    return ''.join([idx_to_char[i] for i in text])  

class TextDataset(Dataset):
    def __init__(self, data, block_size):
        self.data = data
        self.block_size = block_size

    def __len__(self):
        return (len(self.data) - self.block_size - 1) // self.block_size

    def __getitem__(self, idx):
        start_idx = idx * self.block_size
        end_idx = start_idx + self.block_size
        x = self.data[start_idx:end_idx]
        y = self.data[start_idx + 1:end_idx + 1]
        return x, y

def train_val_split(data, split_ratio=0.95):
    n = int(split_ratio*len(data))
    return data[:n], data[n:]

data = torch.tensor(encoder(text), dtype=torch.long)
train, val = train_val_split(data)

train_data = TextDataset(train, block_size)
val_data = TextDataset(val, block_size)
train_loader = DataLoader(train_data, batch_size, shuffle=True)
test_loader = DataLoader(val_data, batch_size, shuffle=False)

model = HourglassLM(vocab_size=vocab_size, n_heads=n_heads, n_embedding=n_embedding, block_size=block_size, factors=factors).to(device)

optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate) # Add weight decay ?
loss_fn = torch.nn.CrossEntropyLoss()

print(f'Parameters: {sum(parameter.numel() for parameter in model.parameters()) / 1e6:.2f}M')
print(f'Vocab_size: {vocab_size}, Block_size: {block_size}, Batch_size: {batch_size}, N_heads: {n_heads}, N_embedding: {n_embedding}')
print(f'Number of chracters in the training dataset: {len(train)}')

starting_time = time.time()

# training loop
for epoch in range(epochs):
    model.train()
    iter_count = 0
    for x, y in tqdm.tqdm(train_loader):
        x, y = x.to(device), y.to(device)

        y_pred = model(x) # (B, T, vocab_size)
        loss = loss_fn(y_pred.view(-1, vocab_size), y.view(-1))

        optimizer.zero_grad()
        loss.backward()
        optimizer.step()

    model.eval()
    with torch.no_grad():
        total_loss = 0
        for x, y in test_loader:
            x, y = x.to(device), y.to(device)
            y_pred = model(x)
            total_loss += loss_fn(y_pred.view(-1, vocab_size), y.view(-1)).item()
        print(f'Epoch: {epoch}, Training Loss: {loss.item()}, Val loss: {total_loss / len(test_loader)}')

end_time = time.time()
print(f'Training time: {end_time - starting_time} seconds')

torch.save(model.state_dict(), 'model_assets/hourglass.pth')