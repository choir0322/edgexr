"""Plot saved visual/gyro comparisons. Optional local Matplotlib dependency."""

import argparse
import csv
import json
from pathlib import Path


def plot_comparisons(folders, output):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    if output.exists():
        raise ValueError('Output already exists; choose a new filename')
    figure, axes = plt.subplots(2,len(folders),figsize=(6*len(folders),6.8),squeeze=False,sharex=True)
    for column, folder in enumerate(folders):
        summary = json.loads((folder/'summary.json').read_text())
        with (folder/'motion.csv').open() as handle:
            rows = list(csv.DictReader(handle))
        good = [r for r in rows if r['accepted']=='True']
        for row_index, key, color, label, bin_key in [
            (0,'horizontal_pixels_s','#156b9a','Image motion (pixels/s at 320×180)','median_horizontal_pixels_s'),
            (1,'gy_dps','#bd5317','Corrected gyro Y (degrees/s)','median_gyro_y_dps')]:
            ax = axes[row_index,column]
            ax.plot([float(r['host_after_cue_s']) for r in good],
                    [float(r[key]) for r in good],color=color,lw=.65,alpha=.5,label='Frame-pair estimate')
            bins = [b for b in summary['per_second'] if b[bin_key] is not None]
            ax.plot([b['second']+.5 for b in bins],[b[bin_key] for b in bins],
                    color=color,lw=2,label='1-second median')
            ax.axhline(0,color='#777777',lw=.7)
            ax.axvspan(0,1,color='#808080',alpha=.12)
            for bad in rows:
                if bad['accepted']!='True':
                    ax.axvline(float(bad['host_after_cue_s']),color='#999999',alpha=.18,lw=1)
            ax.set_xlim(0,15)
            ax.set_ylabel(label)
            ax.grid(alpha=.15)
            ax.spines[['top','right']].set_visible(False)
            if row_index == 1:
                ax.set_xlabel('Seconds after cue (approximate host receipt timing)')
        correlation=summary['horizontal_vs_gyro_y_correlation']
        text=f'r = {correlation:.3f}' if correlation is not None else 'correlation omitted: little motion'
        axes[0,column].set_title(f"{summary['recording']}\n{summary['accepted_pairs']}/{summary['compared_pairs']} accepted pairs; {text}",fontsize=11)
    # Consistent scales make the stationary control directly comparable.
    for row_index in (0,1):
        limits=[ax.get_ylim() for ax in axes[row_index]]
        bound=max(max(abs(a),abs(b)) for a,b in limits)
        for ax in axes[row_index]:
            ax.set_ylim(-bound,bound)
    axes[0,0].legend(loc='upper left',fontsize=8)
    figure.suptitle('Image movement compared with corrected gyro readings',fontsize=15,y=.99)
    figure.text(.5,.01,'Gray start: per-run bias window. Thin gray lines: rejected pairs. Opposite signs reflect image/sensor axes.\nNo fitted time shift, camera calibration, or exposure synchronization.',ha='center',fontsize=9)
    figure.tight_layout(rect=(0,.07,1,.94))
    figure.savefig(output,dpi=170)
    plt.close(figure)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('folders',nargs='+',type=Path)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args()
    plot_comparisons(args.folders,args.output)


if __name__ == '__main__':
    main()
