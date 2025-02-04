import os

import pandas as pd

import jax.numpy as jnp
from jax import random

import cgpax
from analysis.genome_analysis import __load_genome__
from cgpax.jax_evaluation import evaluate_cgp_genome, evaluate_lgp_genome, __evaluate_program_detailed_tracking__
from cgpax.run_utils import __init_environment_from_config__, __update_config_with_env_data__


def compute_rewards_df(genome: jnp.ndarray, rnd_key: random.PRNGKey, config: dict) -> pd.DataFrame:
    env = __init_environment_from_config__(config)
    __update_config_with_env_data__(config, env)
    inner_evaluator = __evaluate_program_detailed_tracking__
    if config["solver"] == "cgp":
        result = evaluate_cgp_genome(genome, rnd_key, config, env, inner_evaluator=inner_evaluator)
    elif config["solver"] == "lgp":
        result = evaluate_lgp_genome(genome, rnd_key, config, env, inner_evaluator=inner_evaluator)
    else:
        raise ValueError
    healthy = result["healthy_rewards"].tolist()
    ctrl = result["ctrl_rewards"].tolist()
    forward = result["forward_rewards"].tolist()
    total = result["total_rewards"].tolist()

    df = pd.DataFrame(list(zip(healthy, ctrl, forward, total)), columns=["healthy", "ctrl", "forward", "total"])
    df["cumulative"] = result["cum_reward"]
    df["cumulative_healthy"] = result["cum_healthy_reward"]
    df["cumulative_ctrl"] = result["cum_ctrl_reward"]
    df["cumulative_forward"] = result["cum_forward_reward"]
    return df


def write_rewards_df(base_path: str, seed: int, generation: int, target_file: str, rnd_key: random.PRNGKey) -> None:
    genome = jnp.load(f"{base_path}/{seed}_{generation}_best_genome.npy", allow_pickle=True).astype(int)
    config = cgpax.get_config(f"{base_path}/config.yaml")
    dataframe = compute_rewards_df(genome, rnd_key, config)
    dataframe.to_csv(target_file, index=False)


if __name__ == '__main__':
    main_target_dir = "data/rewards"
    max_seed = 10

    for outer_seed in range(max_seed):
        for folder in os.listdir("genomes"):
            if not folder.endswith(f"_{outer_seed}"):
                continue

            base_p = f"genomes/{folder}"
            rand_key = random.PRNGKey(outer_seed)
            cfg = cgpax.get_config(f"{base_p}/config.yaml")
            for inner_seed in range(max_seed):
                try:
                    genes, gen = __load_genome__(base_p, inner_seed)
                except FileNotFoundError:
                    continue

                target_f = f"{folder.replace(f'_{outer_seed}', f'_{inner_seed}')}_{gen}.csv"
                if target_f not in os.listdir("data/rewards"):
                    write_rewards_df(base_p, outer_seed, gen, f"data/rewards/{target_f}", rand_key)
                    print(f"{folder} -> {inner_seed}")
