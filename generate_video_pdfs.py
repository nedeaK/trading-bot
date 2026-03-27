import os
import subprocess
import whisper
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER

def extract_frame(video_path, time_sec, output_img):
    cmd = [
        "ffmpeg", "-y",
        "-ss", str(time_sec),
        "-i", video_path,
        "-frames:v", "1",
        "-q:v", "2",
        output_img
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def generate_pdf_for_video(video_path, pdf_path):
    print(f"Loading Whisper model...")
    model = whisper.load_model("base")
    print(f"Transcribing {video_path}...")
    result = model.transcribe(video_path)
    
    segments = result["segments"]
    
    doc = SimpleDocTemplate(pdf_path, pagesize=landscape(letter))
    styles = getSampleStyleSheet()
    
    text_style = styles["Normal"]
    text_style.fontSize = 14
    text_style.leading = 18
    text_style.alignment = TA_CENTER
    
    story = []
    
    print(f"Processing {len(segments)} segments...")
    os.makedirs("temp_frames", exist_ok=True)
    
    for i, seg in enumerate(segments):
        start = seg["start"]
        end = seg["end"]
        text = seg["text"].strip()
        
        if not text:
            continue
            
        # Take a frame from the middle of the segment
        mid_time = start + (end - start) / 2
        
        img_path = f"temp_frames/frame_{i}.jpg"
        extract_frame(video_path, mid_time, img_path)
        
        block = []
        
        # Add to PDF
        if os.path.exists(img_path) and os.path.getsize(img_path) > 0:
            try:
                # 480x270 fits nicely
                img = Image(img_path, width=512, height=288)
                block.append(img)
            except Exception as e:
                print(f"Error loading image {img_path}: {e}")
        
        block.append(Spacer(1, 12))
        block.append(Paragraph(text, text_style))
        block.append(Spacer(1, 24))
        
        story.append(KeepTogether(block))
    
    print("Building PDF...")
    doc.build(story)
    
    # Clean up frames
    try:
        for f in os.listdir("temp_frames"):
            os.remove(os.path.join("temp_frames", f))
        os.rmdir("temp_frames")
    except Exception as e:
        print(f"Cleanup error: {e}")
        
    print(f"Finished {pdf_path}")

if __name__ == "__main__":
    videos = [
        "YTDown.com_YouTube_Liquidity-Structure-Profit_Media_JhBX0TQ41H8_001_1080p.mp4",
        "YTDown.com_YouTube_ULTIMATE-Supply-and-Demand-Masterclass-B_Media_yaCM_cr5BXo_001_1080p.mp4"
    ]
    for v in videos:
        # Save as video name + Document.pdf
        pdf_name = v.replace(".mp4", "_Document.pdf")
        if os.path.exists(v):
            if not os.path.exists(pdf_name):
                generate_pdf_for_video(v, pdf_name)
            else:
                print(f"Skipping {v}, PDF already exists.")
        else:
            print(f"Video {v} not found.")
