import os
import math
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from scipy.special import softmax
from calib_tools import rmsce
import argparse

ANSWER_MAP = {'A': 0, 'B': 1, 'C': 2, 'D': 3}
LABELS = ["label_1", "label_2", "label_3", "label_4"]
MODELS = [
    "model_1",
    "model_2",
    "model_3",
    "model_4",
]
COLORS = [0, 1, 4, 3]
DO_RESCALE=True
TEMPERATURE=np.arange(0.1, 3.1, 0.1)
RESCALE_CONST=0.25

def rescale_softmax_with_temperature(probs, temp, rescale_const):
    probs = np.array(probs)
    return softmax(np.log(probs)/temp)

def compute_calibration_curve(probs, ans):
    diff_bins = np.arange(0, 1.1, 0.1)
    p_correct_list = np.array([]) 
    for i in range(len(diff_bins) - 1):
        lower = diff_bins[i]
        upper = diff_bins[i + 1]
        selected_indices = np.where((probs >= lower) & (probs < upper))
        correct_num = (ans[selected_indices[0]] == selected_indices[1]).sum()

        if len(selected_indices) > 0:
            p_correct = correct_num/len(selected_indices[0])
        else:
            p_correct = None

        p_correct_list = np.append(p_correct_list, p_correct)
    return diff_bins[:-1] + 0.05, p_correct_list

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--n_shots", type=int, default=3)
    args = parser.parse_args()

    k = args.n_shots

    base_dir = "results"
    base_models = [f.split("results_")[1] for f in MODELS if "results" in f]
    models = [os.listdir(f"{base_dir}/results_{base_model}") for base_model in base_models]
    full_model_names = [f"{base_model}/{sub_model}" for base_model, sub_models in zip(base_models, models) for sub_model in sub_models]
    print(full_model_names)

    num_plots = len(full_model_names)
    for temp in TEMPERATURE:

        rows = 1
        cols = num_plots
        positions = range(1, num_plots + 1)

        sns.set_theme(context="paper", font_scale=1.5, style="whitegrid")
        palette = sns.color_palette('colorblind')
        
        fig = plt.figure(1, figsize=(15,5))
        fig.suptitle('MMLU Calibration')
        plt.subplots_adjust(wspace=0.25, left=0.05, right=.95, top=1, bottom=0)


        mses = []

        for k, model in enumerate(full_model_names):
            dir = os.path.join(base_dir, "results_{}".format(model))
            fnames = [f for f in os.listdir(dir) if ".csv" in f]

            all_max_probs = []
            all_cors = []
            all_accs = []
            all_confs = []
            all_probs = []
            all_ans = []

            for fname in fnames:
                subject = fname.split(".csv")[0]
                fpath = os.path.join(dir, fname)
                df = pd.read_csv(fpath)

                correct_answer_column = str(int((df.shape[1]-3)/2 +1))

                max_probs = []
                cors = []
                for i in range(df.shape[0]):
                    probs = [df["{}_choice{}_probs".format(model, choice)][i] for choice in ["A", "B", "C", "D"]]

                    all_ans.append(ANSWER_MAP[df[correct_answer_column][i]])
                    if DO_RESCALE:
                        probs = rescale_softmax_with_temperature(probs, temp, RESCALE_CONST)
                    all_probs.append(probs)
                    
                    cors.append(int(df["{}_correct".format(model)][i]))
                    max_probs.append(np.max(probs))
                all_max_probs += max_probs
                all_cors += cors
                all_accs.append(np.mean(cors))
                all_confs.append(np.mean(max_probs))

            avg_max_prob = np.mean(all_max_probs)
            acc = np.mean(all_cors)
            rms_ce = rmsce(np.array(all_cors), np.array(all_max_probs))
            print("{} overall conf: {:.3f}, acc: {:.3f}, RMS: {:.3f}".format(model, avg_max_prob, acc, rms_ce))

            bins, accuracies = compute_calibration_curve(
                np.array(all_probs),
                np.array(all_ans)
            )
            print(bins)
            print(accuracies)

            mse = ((accuracies-bins)**2).mean(where=~np.isnan(accuracies))
            mses.append(mse)
            print(mse)

            ax = fig.add_subplot(rows, cols, positions[k])
            ax.bar(bins, accuracies, width=0.1, edgecolor="black", label=f"{LABELS[k]}", color=palette[COLORS[k]])
            ax.text(0.25, 0.65, f'MSE:{mse:.3f}', fontsize=14, fontweight='semibold', color='black', horizontalalignment='center')

            x_func = np.linspace(0, 1, 1000)
            y_func = x_func
            ax.plot(x_func, y_func, color='black', linestyle='--', linewidth=3, label="$y=x$")
            ax.set_xlim(0,1)
            ax.set_ylim(0,1)

            ax.set_xlabel('P(answer)')
            ax.set_ylabel('P(correct)')
            ax.legend()
            ax.set_aspect('equal')
        plt.savefig(f"{base_dir}/calibration_curves_temp_{temp}.png")

        # Plot MSE
        plt.clf()
        plt.rcParams.update(plt.rcParamsDefault)
        sns.set_theme(context="paper", font_scale=1.5, style="whitegrid")
        plt.figure()
        plt.bar(LABELS, mses, color=palette[:len(LABELS)])
        plt.title("MSE of calibration against $y=x$")
        plt.xlabel("Model")
        plt.ylabel("MSE")
        plt.savefig(f"{base_dir}/mse_chart_temp_{temp}.png")
