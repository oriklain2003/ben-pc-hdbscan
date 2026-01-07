
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import sklearn.datasets as data
import hdbscan

sns.set_context('poster')
sns.set_style('white')
sns.set_color_codes()
plot_kwds = {'alpha' : 0.5, 's' : 80, 'linewidths':0}

# Generate sample data (similar to the tutorial: moons + blobs)
moons, _ = data.make_moons(n_samples=50, noise=0.05)
blobs, _ = data.make_blobs(n_samples=50, centers=[(-0.75,2.25), (1.0, 2.0)], cluster_std=0.25)
test_data = np.vstack([moons, blobs])

# ============================================
# STEP 1: Visualize the raw data (BEFORE HDBSCAN)
# ============================================
print("Step 1: Raw data visualization (before clustering)")
plt.figure(figsize=(12, 8))
plt.scatter(test_data.T[0], test_data.T[1], color='b', **plot_kwds)
plt.title('Raw Data (Before HDBSCAN Clustering)')
plt.xlabel('Feature 1')
plt.ylabel('Feature 2')
plt.tight_layout()
plt.show()

# ============================================
# STEP 2: Apply HDBSCAN clustering
# ============================================
print("\nStep 2: Applying HDBSCAN clustering...")
clusterer = hdbscan.HDBSCAN(min_cluster_size=5, gen_min_span_tree=True)
cluster_labels = clusterer.fit_predict(test_data)

# ============================================
# STEP 3: Visualize Minimum Spanning Tree
# ============================================
print("\nStep 3: Minimum Spanning Tree visualization")
plt.figure(figsize=(12, 8))
clusterer.minimum_spanning_tree_.plot(edge_cmap='viridis',
                                      edge_alpha=0.6,
                                      node_size=80,
                                      edge_linewidth=2)
plt.title('Minimum Spanning Tree of Mutual Reachability Distance')
plt.tight_layout()
plt.show()

# ============================================
# STEP 4: Visualize Single Linkage Tree (Dendrogram)
# ============================================
print("\nStep 4: Single Linkage Tree (Dendrogram)")
plt.figure(figsize=(12, 8))
clusterer.single_linkage_tree_.plot(cmap='viridis', colorbar=True)
plt.title('Single Linkage Tree (Cluster Hierarchy)')
plt.tight_layout()
plt.show()

# ============================================
# STEP 5: Visualize Condensed Tree
# ============================================
print("\nStep 5: Condensed Tree visualization")
plt.figure(figsize=(12, 8))
clusterer.condensed_tree_.plot()
plt.title('Condensed Cluster Tree')
plt.tight_layout()
plt.show()

# ============================================
# STEP 6: Visualize Condensed Tree with Selected Clusters
# ============================================
print("\nStep 6: Condensed Tree with Selected Clusters")
plt.figure(figsize=(12, 8))
clusterer.condensed_tree_.plot(select_clusters=True, selection_palette=sns.color_palette())
plt.title('Condensed Tree with Selected Clusters (colored)')
plt.tight_layout()
plt.show()

# ============================================
# STEP 7: Final Clustering Result with Membership Probabilities
# ============================================
print("\nStep 7: Final clustering result with membership probabilities")
plt.figure(figsize=(12, 8))
palette = sns.color_palette()
cluster_colors = [sns.desaturate(palette[col], sat)
                  if col >= 0 else (0.5, 0.5, 0.5) for col, sat in
                  zip(clusterer.labels_, clusterer.probabilities_)]
plt.scatter(test_data.T[0], test_data.T[1], c=cluster_colors, **plot_kwds)
plt.title('HDBSCAN Clustering Result\n(Color intensity = membership strength, Gray = noise)')
plt.xlabel('Feature 1')
plt.ylabel('Feature 2')
plt.tight_layout()
plt.show()

# ============================================
# STEP 8: Side-by-side comparison: Before vs After
# ============================================
print("\nStep 8: Side-by-side comparison")
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(20, 8))

# Before clustering
ax1.scatter(test_data.T[0], test_data.T[1], color='b', **plot_kwds)
ax1.set_title('Before HDBSCAN (Raw Data)')
ax1.set_xlabel('Feature 1')
ax1.set_ylabel('Feature 2')

# After clustering
ax2.scatter(test_data.T[0], test_data.T[1], c=cluster_colors, **plot_kwds)
ax2.set_title('After HDBSCAN Clustering\n(Color intensity = membership strength, Gray = noise)')
ax2.set_xlabel('Feature 1')
ax2.set_ylabel('Feature 2')

plt.tight_layout()
plt.show()

# Print clustering statistics
print("\n" + "="*50)
print("Clustering Statistics:")
print("="*50)
print(f"Number of clusters found: {len(set(clusterer.labels_)) - (1 if -1 in clusterer.labels_ else 0)}")
print(f"Number of noise points: {list(clusterer.labels_).count(-1)}")
print(f"Cluster labels: {sorted(set(clusterer.labels_))}")
print(f"Average membership probability: {np.mean(clusterer.probabilities_[clusterer.labels_ >= 0]):.3f}")
print("="*50)