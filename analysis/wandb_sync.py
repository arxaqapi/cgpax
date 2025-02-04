import os
import sys

import pandas as pd
import wandb

from cgpax.run_utils import __update_config_with_env_data__, __init_environment_from_config__, __config_to_run_name__
from cgpax.utils import compute_active_size

import jax.numpy as jnp

if __name__ == '__main__':
    flag = "gp" if len(sys.argv) <= 1 else sys.argv[1].lower()
    assert flag in ["all", "rl", "gp"], "Argument not in the allowed list."

    name_patterns = [] if len(sys.argv) <= 2 else sys.argv[2:]

    os.system("wandb sync")

    api = wandb.Api(timeout=40)
    entity, project = "giorgianadizar", "cgpax"
    runs = api.runs(entity + "/" + project)

    if flag in ["all", "gp"]:
        counter = 0
        for wandb_run in runs:
            if wandb_run.state == "finished" and not wandb_run.name.startswith("RL"):
                process = len(name_patterns) == 0
                for name_pattern in name_patterns:
                    if name_pattern in wandb_run.name:
                        process = True
                        break
                if process:
                    run_name, env_name, solver, ea, fitness, seed = __config_to_run_name__(wandb_run.config,
                                                                                           wandb_run.created_at)
                    wandb_run.name = run_name
                    wandb_run.update()

                    print(f"{counter} -> {run_name}")
                    counter += 1

                    # download history
                    if not os.path.exists(f"data/fitness/{run_name}.csv"):
                        dct = wandb_run.scan_history()
                        df = pd.DataFrame.from_dict(dct)
                        df["solver"] = solver
                        df["ea"] = ea
                        df["fitness"] = fitness
                        df["environment"] = env_name
                        df["seed"] = df["training.run_id"] if wandb_run.config.get("n_parallel_runs", 0) > 1 else \
                            wandb_run.config[
                                "seed"]
                        df["training.evaluation"] = df["training.generation"] * wandb_run.config["n_individuals"]
                        for i in range(3):
                            if f"training.top_k_reward.top_{i}_reward" not in df.columns:
                                df[f"training.top_k_reward.top_{i}_reward"] = df[f"training.top_k_fit.top_{i}_fit"]

                        # top_k_reward
                        df.to_csv(f"data/fitness/{run_name}.csv")

                    # download genomes
                    target_dir = f"../analysis/genomes/{wandb_run.name}"
                    if not os.path.exists(target_dir):
                        os.makedirs(target_dir)
                        files = wandb_run.files()
                        for file in files:
                            if file.name.startswith("genomes/") or file.name == "config.yaml":
                                file.name = file.name.replace("genomes/", "")
                                file.download(root=target_dir)

                        # compute graph sizes
                        graph_sizes = []
                        environment = __init_environment_from_config__(wandb_run.config)
                        __update_config_with_env_data__(wandb_run.config, environment)

                        file_names = [f for f in os.listdir(f"{target_dir}/") if f != "config.yaml"]
                        for file_name in file_names:
                            genome = jnp.load(f"{target_dir}/{file_name}", allow_pickle=True).astype(int)
                            graph_size, max_size = compute_active_size(genome, wandb_run.config)
                            info = file_name.split("_")
                            seed = info[0] if wandb_run.config.get("n_parallel_runs", 0) > 1 else wandb_run.config[
                                "seed"]
                            generation = info[1]
                            graph_sizes.append({
                                "seed": str(seed),
                                "generation": generation,
                                "evaluation": generation * wandb_run.config["n_individuals"],
                                "graph_size": graph_size,
                                "max_size": max_size
                            })
                        graph_df = pd.DataFrame.from_dict(graph_sizes)
                        graph_df["solver"] = solver
                        graph_df["ea"] = ea
                        graph_df["fitness"] = fitness
                        graph_df["environment"] = env_name
                        graph_df.to_csv(f"data/graph_size/{run_name}.csv")

    if flag in ["all", "rl"]:
        counter = 0
        for wandb_run in runs:
            if wandb_run.state == "finished" and wandb_run.name.startswith("RL") and not os.path.exists(
                    f"data/rl/{wandb_run.name.replace('RL_', '')}.csv"):
                process = len(name_patterns) == 0
                for name_pattern in name_patterns:
                    if name_pattern in wandb_run.name:
                        process = True
                        break
                if process:
                    print(f"{counter} -> {wandb_run.name}")
                    counter += 1

                    # download history
                    split_name = wandb_run.name.split("_")
                    ddf = wandb_run.history(pandas=True)
                    ddf["seed"] = split_name[-1]
                    ddf["rl_algorithm"] = split_name[-2]
                    ddf["environment"] = "_".join(split_name[1:-2])
                    ddf.to_csv(f"data/rl/{wandb_run.name.replace('RL_', '')}.csv")
